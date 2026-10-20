"""Durable goals and the execution profiles they run under (PA-D01, PA-D02).

A goal is an outcome the owner can return to: success criteria, a plan of steps
and a status the server owns. Its steps run as ordinary governed tasks, so the
coordinator here composes existing task execution and never adds a second tool
broker. An execution profile is the Settings-owned ceiling on which models a
goal's work may reach and what may leave the host with it.
"""
