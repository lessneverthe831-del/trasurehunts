"""Multi-Stage Checkpoints and QR Code Definitions
"""

CHECKPOINTS = [
    {
        "stage": 2,
        "checkpoint_id": "chkp-library-9a1b",
        "title": "Checkpoint 1: The Library Archives",
        "location": "Library Archives - 2nd Floor West Wing",
        "clue": "Navigate to the quiet corridor on the 2nd floor of the West Wing. Look near the ancient history archives behind the grandfather clock.",
        "badge_icon": "📚"
    },
    {
        "stage": 3,
        "checkpoint_id": "chkp-robotics-7c2d",
        "title": "Checkpoint 2: The Robotics & AI Lab",
        "location": "Robotics Lab - Ground Floor Bay B",
        "clue": "Descend to the ground floor engineering lab. The next QR marker is affixed beside the main terminal of Robotic Arm #3.",
        "badge_icon": "🤖"
    },
    {
        "stage": 4,
        "checkpoint_id": "chkp-observatory-4e8f",
        "title": "Checkpoint 3: The Observatory Courtyard",
        "location": "Observatory Courtyard - Bronze Sundial",
        "clue": "Step out into the open courtyard toward the astronomical observatory. Inspect the bronze pedestal of the central sundial.",
        "badge_icon": "🔭"
    },
    {
        "stage": 5,
        "checkpoint_id": "chkp-vault-omega-01",
        "title": "Final Checkpoint: The Central Vault",
        "location": "Central Vault Room - Sub-level Alpha",
        "clue": "Proceed through the security hatch down to the Sub-level Alpha. The final authentication node awaits on the primary mainframe terminal.",
        "badge_icon": "🏆",
        "is_final": True
    }
]

# Lookup map by checkpoint_id
CHECKPOINTS_BY_ID = {c["checkpoint_id"]: c for c in CHECKPOINTS}
CHECKPOINTS_BY_STAGE = {c["stage"]: c for c in CHECKPOINTS}


def get_checkpoint_by_id(chkp_id: str):
    return CHECKPOINTS_BY_ID.get(chkp_id)


def get_checkpoint_for_stage(stage_num: int):
    return CHECKPOINTS_BY_STAGE.get(stage_num)


def get_next_checkpoint(current_stage_num: int):
    return CHECKPOINTS_BY_STAGE.get(current_stage_num + 1)
