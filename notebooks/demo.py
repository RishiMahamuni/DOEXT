# langgraph_batch_pipeline.py
"""
LangGraph batch pipeline with:
- Cached DSPy module instances (Extractor/Normalizer/Judge built once)
- Batch processing over many docs
- Retry loop: if Judge marks any field INVALID/FAILED, rerun the full pipeline
  (you can optimize later to rerun only failed groups/fields)

You already have these builders implemented and working:
  - BuildFieldExtractorModule
  - BuildFieldNormalizerModule
  - BuildFieldJudgeModule

Update the imports below to match your project paths.
"""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict

from langgraph.graph import StateGraph, START, END

# ✅ Adjust these imports to your repo



# ============================
# State
# ============================

class DocItem(TypedDict, total=False):
    doc_id: str
    doc_text: str


class BatchResult(TypedDict, total=False):
    doc_id: str
    extracted: Dict[str, Dict[str, Any]]
    normalized: Dict[str, Dict[str, Any]]
    verdicts: Dict[str, Dict[str, Any]]
    errors: Dict[str, str]


class RuntimeCache(TypedDict, total=False):
    extractor: Any
    normalizer: Any
    judge: Any


class BatchState(TypedDict, total=False):
    # config schemas (your Pydantic objects)
    groups_schema: Any
    modules_schema: Any

    # input docs
    docs: List[DocItem]

    # cached module instances
    runtime: RuntimeCache

    # output per doc
    results: List[BatchResult]

    # control
    extractor_module_name: str
    normalizer_module_name: str
    judge_module_name: str
    normalizer_max_iters: int

    max_retries: int
    retry_count: int


# ============================
# Helpers
# ============================

def _is_fail_verdict(verdict: Any) -> bool:
    """
    Decide if a verdict implies failure.
    Customize this to match your Judge output contract.
    """
    if verdict is None:
        return False
    s = str(verdict).strip().lower()
    return ("invalid" in s) or ("fail" in s) or ("failed" in s)


# ============================
# Nodes
# ============================

def init_runtime_node(state: BatchState) -> BatchState:
    """
    Build & cache DSPy module instances ONCE.
    """
    extractor_name = state.get("extractor_module_name", "FieldExtractor")
    normalizer_name = state.get("normalizer_module_name", "FieldNormalizer")
    judge_name = state.get("judge_module_name", "Judge")

    max_iters = int(state.get("normalizer_max_iters", 5))
    state["retry_count"] = int(state.get("retry_count", 0))
    state["max_retries"] = int(state.get("max_retries", 0))

    ExtractorCls = BuildFieldExtractorModule(
        module_name=extractor_name,
        groups_schema=state["groups_schema"],
        modules_schema=state["modules_schema"],
    )
    NormalizerCls = BuildFieldNormalizerModule(
        module_name=normalizer_name,
        groups_schema=state["groups_schema"],
        modules_schema=state["modules_schema"],
        max_iters=max_iters,
    )
    JudgeCls = BuildFieldJudgeModule(
        module_name=judge_name,
        groups_schema=state["groups_schema"],
        modules_schema=state["modules_schema"],
    )

    state["runtime"] = {
        "extractor": ExtractorCls(),
        "normalizer": NormalizerCls(),
        "judge": JudgeCls(),
    }
    state["results"] = []
    return state


def process_batch_node(state: BatchState) -> BatchState:
    """
    Run Extract -> Normalize -> Judge for every doc in state["docs"].
    Results stored in state["results"].
    """
    extractor = state["runtime"]["extractor"]
    normalizer = state["runtime"]["normalizer"]
    judge = state["runtime"]["judge"]

    results: List[BatchResult] = []

    for i, doc in enumerate(state.get("docs", [])):
        doc_id = doc.get("doc_id", str(i))
        doc_text = doc.get("doc_text", "")

        item: BatchResult = {"doc_id": doc_id}
        errors: Dict[str, str] = {}

        # Extract
        try:
            extracted = extractor(doc_text=doc_text)
            item["extracted"] = extracted
        except Exception as e:
            errors["extractor"] = str(e)
            item["extracted"] = {}

        # Normalize
        try:
            normalized = normalizer(extracted=item.get("extracted", {}))
            item["normalized"] = normalized
        except Exception as e:
            errors["normalizer"] = str(e)
            item["normalized"] = {}

        # Judge
        try:
            verdicts = judge(
                doc_text=doc_text,
                extracted=item.get("extracted", {}),
                normalized=item.get("normalized", {}),
            )
            item["verdicts"] = verdicts
        except Exception as e:
            errors["judge"] = str(e)
            item["verdicts"] = {}

        if errors:
            item["errors"] = errors

        results.append(item)

    state["results"] = results
    return state


def should_retry_node(state: BatchState) -> str:
    """
    Conditional node:
    - If any doc has any failed verdict AND retry_count < max_retries -> rerun process_batch
    - Else -> END
    """
    max_retries = int(state.get("max_retries", 0))
    retry_count = int(state.get("retry_count", 0))

    any_failed = False
    for item in state.get("results", []):
        verdicts = item.get("verdicts", {}) or {}
        for group_map in verdicts.values():
            if not isinstance(group_map, dict):
                continue
            for v in group_map.values():
                if _is_fail_verdict(v):
                    any_failed = True
                    break
            if any_failed:
                break
        if any_failed:
            break

    if any_failed and retry_count < max_retries:
        state["retry_count"] = retry_count + 1
        return "process_batch"

    return END


# ============================
# Graph builder
# ============================

def build_langgraph_batch_pipeline() -> Any:
    g = StateGraph(BatchState)

    g.add_node("init_runtime", init_runtime_node)
    g.add_node("process_batch", process_batch_node)
    g.add_node("should_retry", should_retry_node)

    g.add_edge(START, "init_runtime")
    g.add_edge("init_runtime", "process_batch")
    g.add_edge("process_batch", "should_retry")

    # conditional edges: should_retry_node returns either "process_batch" or END
    g.add_conditional_edges(
        "should_retry",
        should_retry_node,
        {
            "process_batch": "process_batch",
            END: END,
        },
    )

    return g.compile()


# ============================
# Example usage
# ============================

if __name__ == "__main__":
    # You already create these from YAML -> Pydantic parsing
    # groups_schema = ...
    # modules_schema = ...

    docs = [
        {"doc_id": "inv_1", "doc_text": "Invoice No: INV-0098\nInvoice Date: 12/01/24\nTotal: ₹ 3,894.00\n"},
        {"doc_id": "inv_2", "doc_text": "Invoice ID: A-77\nDate: 2024-02-05\nGrand Total: 1299.50\n"},
    ]

    graph = build_langgraph_batch_pipeline()

    final_state = graph.invoke({
        "groups_schema": groups_schema,
        "modules_schema": modules_schema,
        "docs": docs,
        "max_retries": 2,
        "retry_count": 0,
        # Optional overrides:
        "extractor_module_name": "FieldExtractor",
        "normalizer_module_name": "FieldNormalizer",
        "judge_module_name": "Judge",
        "normalizer_max_iters": 5,
    })

    print("retry_count:", final_state.get("retry_count"))
    for r in final_state.get("results", []):
        print("\n====================")
        print("doc_id:", r.get("doc_id"))
        print("EXTRACTED:", r.get("extracted"))
        print("NORMALIZED:", r.get("normalized"))
        print("VERDICTS:", r.get("verdicts"))
        if r.get("errors"):
            print("ERRORS:", r["errors"])
