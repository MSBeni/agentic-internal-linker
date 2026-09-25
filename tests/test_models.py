from agentic_internal_linker import link_document


def test_serialized_report_omits_document_content_by_default() -> None:
    document_text = "A private internal linking guide helps editors.\n"
    result = link_document(
        document_text,
        [{"url": "https://example.com/linking", "title": "Internal Linking Guide"}],
        base_url="https://example.com",
    )

    safe_value = result.to_dict()
    full_value = result.to_dict(include_content=True)
    assert document_text not in repr(safe_value)
    assert "linked_markdown" not in safe_value
    assert "linked_markdown" in full_value
