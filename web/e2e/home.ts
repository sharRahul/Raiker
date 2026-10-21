/**
 * QUI-H01 — what Home's heading reads.
 *
 * "Welcome" on a first day, then a greeting for the time of day, each followed
 * by the owner's name when one is set. Specs that wait for Home to be on screen
 * match this rather than a fixed string, so a morning run and an evening run
 * both recognise the same page.
 */
export const HOME_GREETING = /^(Welcome|Good (morning|afternoon|evening))(, .+)?$/;
