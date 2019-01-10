from eth2.beacon.types.candidate_pow_receipt_root_records import (
    CandidatePoWReceiptRootRecord,
)


def test_defaults(sample_candidate_pow_receipt_root_record_params):
    candidate_pow_receipt_roots = CandidatePoWReceiptRootRecord(
        **sample_candidate_pow_receipt_root_record_params
    )
    assert candidate_pow_receipt_roots.candidate_pow_receipt_root == sample_candidate_pow_receipt_root_record_params['candidate_pow_receipt_root']  # noqa: E501
    assert candidate_pow_receipt_roots.votes == sample_candidate_pow_receipt_root_record_params['votes']  # noqa: E501
