//! Loopback filtering for the restricted account, through the Windows
//! Filtering Platform.
//!
//! Windows Firewall does not filter loopback, so the account's outbound block
//! left every local service reachable: anything listening on `127.0.0.1` or
//! on one of this machine's own addresses (a database, a dev server, Raiker's
//! own API). These filters close that, from the *listener's* side: the accept
//! layer knows both who is listening (`ALE_USER_ID`) and, for a local
//! connection, who is connecting (`ALE_REMOTE_USER_ID`). In one sublayer:
//!
//! * permit when the listener is the account itself, because toolchains
//!   connect to their own listeners (Python's asyncio builds its wake-up
//!   socket pair over loopback on Windows);
//! * permit to Raiker's download-proxy ports, the one local service a run is
//!   meant to reach;
//! * block every other local connection the account makes.
//!
//! The filters are persistent and keyed by fixed GUIDs, so setup replaces them
//! and reset removes them. Whether they hold is measured by the probe, with an
//! owner-side control arm; nothing here is assumed to work.

use super::*;
use windows_sys::Win32::Foundation::{
    FWP_E_ALREADY_EXISTS, FWP_E_FILTER_NOT_FOUND, FWP_E_PROVIDER_NOT_FOUND,
    FWP_E_SUBLAYER_NOT_FOUND,
};
use windows_sys::Win32::NetworkManagement::WindowsFilteringPlatform::{
    FWP_ACTION_BLOCK, FWP_ACTION_PERMIT, FWP_BYTE_BLOB, FWP_CONDITION_FLAG_IS_LOOPBACK,
    FWP_CONDITION_VALUE0, FWP_CONDITION_VALUE0_0, FWP_MATCH_EQUAL, FWP_MATCH_FLAGS_ALL_SET,
    FWP_MATCH_RANGE, FWP_RANGE_TYPE, FWP_RANGE0, FWP_SECURITY_DESCRIPTOR_TYPE, FWP_UINT8,
    FWP_UINT16, FWP_UINT32, FWP_VALUE0, FWP_VALUE0_0, FWPM_ACTION0,
    FWPM_CONDITION_ALE_REMOTE_USER_ID, FWPM_CONDITION_ALE_USER_ID, FWPM_CONDITION_FLAGS,
    FWPM_CONDITION_IP_LOCAL_PORT, FWPM_DISPLAY_DATA0, FWPM_FILTER_CONDITION0,
    FWPM_FILTER_FLAG_PERSISTENT, FWPM_FILTER0, FWPM_LAYER_ALE_AUTH_RECV_ACCEPT_V4,
    FWPM_LAYER_ALE_AUTH_RECV_ACCEPT_V6, FWPM_PROVIDER_FLAG_PERSISTENT, FWPM_PROVIDER0,
    FWPM_SUBLAYER_FLAG_PERSISTENT, FWPM_SUBLAYER0, FwpmEngineClose0, FwpmEngineOpen0,
    FwpmFilterAdd0, FwpmFilterDeleteByKey0, FwpmProviderAdd0, FwpmProviderDeleteByKey0,
    FwpmSubLayerAdd0, FwpmSubLayerDeleteByKey0, FwpmTransactionAbort0, FwpmTransactionBegin0,
    FwpmTransactionCommit0,
};
use windows_sys::Win32::Security::GetSecurityDescriptorLength;
use windows_sys::core::GUID;

/// The ports Raiker's per-run download proxy listens on when commands run as
/// the account (`raiker/execution/commands/egress_runtime.py` uses the same
/// range). A run is allowed to reach these and no other local port.
pub const PROXY_PORT_LOW: u16 = 47300;
pub const PROXY_PORT_HIGH: u16 = 47363;

const RPC_C_AUTHN_WINNT: u32 = 10;

const PROVIDER: GUID = GUID::from_u128(0x5c0d_3b6e_8f2a_4c71_9a4e_1d2b_7e6f_a001);
const SUBLAYER: GUID = GUID::from_u128(0x5c0d_3b6e_8f2a_4c71_9a4e_1d2b_7e6f_a002);
/// One key per filter and address family, in the order [`filters`] builds them.
const FILTERS: [GUID; 6] = [
    GUID::from_u128(0x5c0d_3b6e_8f2a_4c71_9a4e_1d2b_7e6f_a010),
    GUID::from_u128(0x5c0d_3b6e_8f2a_4c71_9a4e_1d2b_7e6f_a011),
    GUID::from_u128(0x5c0d_3b6e_8f2a_4c71_9a4e_1d2b_7e6f_a012),
    GUID::from_u128(0x5c0d_3b6e_8f2a_4c71_9a4e_1d2b_7e6f_a013),
    GUID::from_u128(0x5c0d_3b6e_8f2a_4c71_9a4e_1d2b_7e6f_a014),
    GUID::from_u128(0x5c0d_3b6e_8f2a_4c71_9a4e_1d2b_7e6f_a015),
];

/// What each filter does, before it is turned into WFP structures.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Rule {
    /// The listener is the account: its own socket pairs and servers.
    OwnListener,
    /// The listener is on a download-proxy port.
    ProxyPort,
    /// Anything else on this machine, reached by the account.
    BlockLocal,
}

impl Rule {
    fn weight(self) -> u8 {
        match self {
            Rule::OwnListener => 15,
            Rule::ProxyPort => 14,
            Rule::BlockLocal => 10,
        }
    }
}

/// `(key, layer, rule)` for every filter setup installs.
pub fn filters() -> Vec<(GUID, GUID, Rule)> {
    let mut out = Vec::new();
    let mut keys = FILTERS.iter();
    for layer in [
        FWPM_LAYER_ALE_AUTH_RECV_ACCEPT_V4,
        FWPM_LAYER_ALE_AUTH_RECV_ACCEPT_V6,
    ] {
        for rule in [Rule::OwnListener, Rule::ProxyPort, Rule::BlockLocal] {
            out.push((*keys.next().expect("one key per filter"), layer, rule));
        }
    }
    out
}

struct Engine(HANDLE);

impl Engine {
    fn open() -> Result<Engine, String> {
        let mut handle: HANDLE = null_mut();
        let code =
            unsafe { FwpmEngineOpen0(null(), RPC_C_AUTHN_WINNT, null(), null(), &mut handle) };
        if code != 0 {
            return Err(format!("native_sandbox_account_wfp_unavailable:{code:#x}"));
        }
        Ok(Engine(handle))
    }
}

impl Drop for Engine {
    fn drop(&mut self) {
        unsafe { FwpmEngineClose0(self.0) };
    }
}

/// A self-relative security descriptor granting only *sid*, the form WFP's
/// user-id conditions are matched against.
struct Descriptor(PSECURITY_DESCRIPTOR);

impl Descriptor {
    fn for_sid(sid_text: &str) -> Result<Descriptor, String> {
        let text = wide(&format!("D:(A;;CC;;;{sid_text})"));
        let mut descriptor: PSECURITY_DESCRIPTOR = null_mut();
        if unsafe {
            ConvertStringSecurityDescriptorToSecurityDescriptorW(
                text.as_ptr(),
                SDDL_REVISION_1,
                &mut descriptor,
                null_mut(),
            )
        } == 0
        {
            return Err("native_sandbox_account_wfp_failed".into());
        }
        Ok(Descriptor(descriptor))
    }

    fn blob(&self) -> FWP_BYTE_BLOB {
        FWP_BYTE_BLOB {
            size: unsafe { GetSecurityDescriptorLength(self.0) },
            data: self.0 as *mut u8,
        }
    }
}

impl Drop for Descriptor {
    fn drop(&mut self) {
        unsafe { LocalFree(self.0 as HLOCAL) };
    }
}

/// Install (or replace) the provider, sublayer and filters for *account_sid*.
pub fn install(account_sid: &str) -> Result<(), String> {
    let engine = Engine::open()?;
    let descriptor = Descriptor::for_sid(account_sid)?;
    transaction(&engine, |engine| {
        remove_all(engine)?;
        add_provider(engine)?;
        add_sublayer(engine)?;
        for (key, layer, rule) in filters() {
            add_filter(engine, key, layer, rule, &descriptor)?;
        }
        Ok(())
    })
}

/// Remove everything [`install`] added. Missing pieces are not an error.
pub fn remove() -> Result<(), String> {
    let engine = Engine::open()?;
    transaction(&engine, remove_all)
}

fn transaction(
    engine: &Engine,
    body: impl FnOnce(&Engine) -> Result<(), String>,
) -> Result<(), String> {
    if unsafe { FwpmTransactionBegin0(engine.0, 0) } != 0 {
        return Err("native_sandbox_account_wfp_failed".into());
    }
    match body(engine) {
        Ok(()) => {
            if unsafe { FwpmTransactionCommit0(engine.0) } == 0 {
                Ok(())
            } else {
                Err("native_sandbox_account_wfp_failed".into())
            }
        }
        Err(reason) => {
            unsafe { FwpmTransactionAbort0(engine.0) };
            Err(reason)
        }
    }
}

fn remove_all(engine: &Engine) -> Result<(), String> {
    for key in FILTERS {
        tolerate(
            unsafe { FwpmFilterDeleteByKey0(engine.0, &key) },
            FWP_E_FILTER_NOT_FOUND,
        )?;
    }
    tolerate(
        unsafe { FwpmSubLayerDeleteByKey0(engine.0, &SUBLAYER) },
        FWP_E_SUBLAYER_NOT_FOUND,
    )?;
    tolerate(
        unsafe { FwpmProviderDeleteByKey0(engine.0, &PROVIDER) },
        FWP_E_PROVIDER_NOT_FOUND,
    )
}

fn tolerate(code: u32, absent: i32) -> Result<(), String> {
    if code == 0 || code == absent as u32 {
        Ok(())
    } else {
        Err(format!("native_sandbox_account_wfp_failed:{code:#x}"))
    }
}

fn display(name: &[u16]) -> FWPM_DISPLAY_DATA0 {
    FWPM_DISPLAY_DATA0 {
        name: name.as_ptr() as *mut u16,
        description: null_mut(),
    }
}

fn add_provider(engine: &Engine) -> Result<(), String> {
    let name = wide("Raiker sandbox");
    let provider = FWPM_PROVIDER0 {
        providerKey: PROVIDER,
        displayData: display(&name),
        flags: FWPM_PROVIDER_FLAG_PERSISTENT,
        ..Default::default()
    };
    added(unsafe { FwpmProviderAdd0(engine.0, &provider, null_mut()) })
}

fn add_sublayer(engine: &Engine) -> Result<(), String> {
    let name = wide("Raiker sandbox: loopback");
    let mut provider = PROVIDER;
    let sublayer = FWPM_SUBLAYER0 {
        subLayerKey: SUBLAYER,
        displayData: display(&name),
        flags: FWPM_SUBLAYER_FLAG_PERSISTENT,
        providerKey: &mut provider,
        weight: 0x8000,
        ..Default::default()
    };
    added(unsafe { FwpmSubLayerAdd0(engine.0, &sublayer, null_mut()) })
}

fn added(code: u32) -> Result<(), String> {
    if code == 0 || code == FWP_E_ALREADY_EXISTS as u32 {
        Ok(())
    } else {
        Err(format!("native_sandbox_account_wfp_failed:{code:#x}"))
    }
}

fn user_condition(field: GUID, blob: &mut FWP_BYTE_BLOB) -> FWPM_FILTER_CONDITION0 {
    FWPM_FILTER_CONDITION0 {
        fieldKey: field,
        matchType: FWP_MATCH_EQUAL,
        conditionValue: FWP_CONDITION_VALUE0 {
            r#type: FWP_SECURITY_DESCRIPTOR_TYPE,
            Anonymous: FWP_CONDITION_VALUE0_0 { sd: blob },
        },
    }
}

fn add_filter(
    engine: &Engine,
    key: GUID,
    layer: GUID,
    rule: Rule,
    descriptor: &Descriptor,
) -> Result<(), String> {
    let mut account = descriptor.blob();
    let mut ports = FWP_RANGE0 {
        valueLow: FWP_VALUE0 {
            r#type: FWP_UINT16,
            Anonymous: FWP_VALUE0_0 {
                uint16: PROXY_PORT_LOW,
            },
        },
        valueHigh: FWP_VALUE0 {
            r#type: FWP_UINT16,
            Anonymous: FWP_VALUE0_0 {
                uint16: PROXY_PORT_HIGH,
            },
        },
    };
    let mut conditions: Vec<FWPM_FILTER_CONDITION0> = match rule {
        Rule::OwnListener => vec![user_condition(FWPM_CONDITION_ALE_USER_ID, &mut account)],
        Rule::ProxyPort => vec![FWPM_FILTER_CONDITION0 {
            fieldKey: FWPM_CONDITION_IP_LOCAL_PORT,
            matchType: FWP_MATCH_RANGE,
            conditionValue: FWP_CONDITION_VALUE0 {
                r#type: FWP_RANGE_TYPE,
                Anonymous: FWP_CONDITION_VALUE0_0 {
                    rangeValue: &mut ports,
                },
            },
        }],
        Rule::BlockLocal => vec![
            FWPM_FILTER_CONDITION0 {
                fieldKey: FWPM_CONDITION_FLAGS,
                matchType: FWP_MATCH_FLAGS_ALL_SET,
                conditionValue: FWP_CONDITION_VALUE0 {
                    r#type: FWP_UINT32,
                    Anonymous: FWP_CONDITION_VALUE0_0 {
                        uint32: FWP_CONDITION_FLAG_IS_LOOPBACK,
                    },
                },
            },
            user_condition(FWPM_CONDITION_ALE_REMOTE_USER_ID, &mut account),
        ],
    };
    let name = wide(match rule {
        Rule::OwnListener => "Raiker sandbox: permit its own listeners",
        Rule::ProxyPort => "Raiker sandbox: permit the download proxy",
        Rule::BlockLocal => "Raiker sandbox: block local services",
    });
    let mut provider = PROVIDER;
    let filter = FWPM_FILTER0 {
        filterKey: key,
        displayData: display(&name),
        flags: FWPM_FILTER_FLAG_PERSISTENT,
        providerKey: &mut provider,
        layerKey: layer,
        subLayerKey: SUBLAYER,
        weight: FWP_VALUE0 {
            r#type: FWP_UINT8,
            Anonymous: FWP_VALUE0_0 {
                uint8: rule.weight(),
            },
        },
        numFilterConditions: conditions.len() as u32,
        filterCondition: conditions.as_mut_ptr(),
        action: FWPM_ACTION0 {
            r#type: if rule == Rule::BlockLocal {
                FWP_ACTION_BLOCK
            } else {
                FWP_ACTION_PERMIT
            },
            ..Default::default()
        },
        ..Default::default()
    };
    let mut id = 0u64;
    let code = unsafe { FwpmFilterAdd0(engine.0, &filter, null_mut(), &mut id) };
    if code == 0 {
        Ok(())
    } else {
        Err(format!("native_sandbox_account_wfp_failed:{code:#x}"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_filter_has_its_own_key_and_the_block_weighs_least() {
        let filters = filters();
        assert_eq!(filters.len(), FILTERS.len());
        let mut keys: Vec<(u32, u16, u16, [u8; 8])> = filters
            .iter()
            .map(|(key, _, _)| (key.data1, key.data2, key.data3, key.data4))
            .collect();
        keys.sort_unstable();
        keys.dedup();
        assert_eq!(keys.len(), FILTERS.len());
        assert!(Rule::BlockLocal.weight() < Rule::ProxyPort.weight());
        assert!(Rule::ProxyPort.weight() < Rule::OwnListener.weight());
    }

    #[test]
    fn the_proxy_range_matches_egress_runtime() {
        let source = include_str!("../../../raiker/execution/commands/egress_runtime.py");
        assert!(source.contains(&format!(
            "WINDOWS_PROXY_PORTS = range({PROXY_PORT_LOW}, {})",
            PROXY_PORT_HIGH + 1
        )));
    }
}
