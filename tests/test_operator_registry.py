# -*- coding: utf-8 -*-

from data_juicer_agents.tools.op_manager.operator_registry import resolve_operator_name


def test_resolve_operator_name_exact_match():
    ops = {"document_minhash_deduplicator", "text_length_filter"}
    assert (
        resolve_operator_name("document_minhash_deduplicator", available_ops=ops)
        == "document_minhash_deduplicator"
    )


def test_resolve_operator_name_from_camel_case():
    ops = {"document_minhash_deduplicator", "text_length_filter"}
    assert (
        resolve_operator_name("DocumentMinHashDeduplicator", available_ops=ops)
        == "document_minhash_deduplicator"
    )


def test_resolve_operator_name_unknown_kept():
    ops = {"document_minhash_deduplicator", "text_length_filter"}
    assert (
        resolve_operator_name("non_existing_operator_for_test", available_ops=ops)
        == "non_existing_operator_for_test"
    )
