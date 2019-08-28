from ssz.tools import to_formatted_dict

from eth2.beacon.types.states import BeaconState


def validate_state(post_state: BeaconState, expected_state: BeaconState) -> None:
    # Use dict diff, easier to see the diff
    dict_post_state = to_formatted_dict(post_state, BeaconState)
    dict_expected_state = to_formatted_dict(expected_state, BeaconState)
    for key, value in dict_expected_state.items():
        if isinstance(value, list):
            value = tuple(value)
        if dict_post_state[key] != value:
            raise AssertionError(
                f"state.{key} is incorrect:\n"
                f"\tExpected: {value}\n"
                f"\tResult: {dict_post_state[key]}\n"
            )
