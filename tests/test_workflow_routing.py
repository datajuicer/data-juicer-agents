# -*- coding: utf-8 -*-

from data_juicer_agents.tools.router_helpers import retrieve_workflow, select_workflow


def test_select_workflow_for_rag():
    workflow = select_workflow("please clean rag corpus and retrieval chunks")
    assert workflow == "rag_cleaning"


def test_select_workflow_for_multimodal_dedup():
    workflow = select_workflow("do image duplicate removal for multimodal dataset")
    assert workflow == "multimodal_dedup"


def test_select_workflow_prefers_rag_for_text_dedup_only():
    workflow = select_workflow("prepare rag documents: normalize, length filter, deduplicate")
    assert workflow == "rag_cleaning"


def test_select_workflow_prefers_multimodal_for_image_cues():
    workflow = select_workflow("图文数据近重复清理，降低训练数据冗余")
    assert workflow == "multimodal_dedup"


def test_select_workflow_prefers_multimodal_for_multimodal_keyword():
    workflow = select_workflow("对多模态数据集做重复样本过滤")
    assert workflow == "multimodal_dedup"


def test_retrieve_workflow_returns_none_when_intent_has_no_template_signal():
    workflow = retrieve_workflow("帮我做一些处理")
    assert workflow is None


def test_select_workflow_still_defaults_to_rag_when_retrieve_returns_none():
    workflow = select_workflow("帮我做一些处理")
    assert workflow == "rag_cleaning"
