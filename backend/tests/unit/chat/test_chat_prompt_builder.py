from __future__ import annotations

"""Unit tests for `app.services.chat.prompt_builder` (Plan 08-04 Task 2).

Coverage per <behavior> Tests PB1-PB6:
  - PB1: build_system_prompt() returns list[dict] of len >= 2 (D-26)
  - PB2: last item has cache_control={"type": "ephemeral"} (D-27 — LM-6)
  - PB3: text contains all 6 Sofa Belle salesperson full names (D-09 / D-26)
  - PB4: text contains the MVP1 data-limits block (Meta/Google/TikTok/GA4/GSC)
  - PB5: text contains showrooms (Brașov / București / Cluj-Napoca)
  - PB6: text instructs markdown link format [Label](/sales) (D-18)
"""


class TestPromptBuilder:
    def test_pb1_returns_list_of_blocks(self) -> None:
        from app.services.chat.prompt_builder import (
            _build_tenant_facts,
            build_system_prompt,
        )

        blocks = build_system_prompt(_build_tenant_facts())
        assert isinstance(blocks, list)
        assert len(blocks) >= 2
        for blk in blocks:
            assert isinstance(blk, dict)
            assert blk.get("type") == "text"
            assert isinstance(blk.get("text"), str)
            assert blk["text"]  # non-empty

    def test_pb2_cache_control_marks_cached_prefix_end(self) -> None:
        from app.services.chat.prompt_builder import (
            _build_tenant_facts,
            build_system_prompt,
        )

        blocks = build_system_prompt(_build_tenant_facts())
        # D-27 — cache_control marks the END of the cached prefix. Originally
        # the OUTPUT_FORMAT block was the last block. After the today-block
        # injection (current-date fix), a dynamic today block is appended
        # AFTER the sentinel so the cached prefix above stays stable across
        # days while Claude still sees today's date. The sentinel is at [-2].
        sentinel = blocks[-2]
        assert sentinel.get("cache_control") == {"type": "ephemeral"}
        # The tail block is the dynamic today-context block; it MUST NOT carry
        # cache_control (would defeat the entire prefix cache).
        assert blocks[-1].get("cache_control") is None
        assert "Data curentă:" in blocks[-1]["text"]

    def test_pb3_six_salesperson_full_names(self) -> None:
        from app.services.chat.prompt_builder import (
            _build_tenant_facts,
            build_system_prompt,
        )

        blocks = build_system_prompt(_build_tenant_facts())
        text = "\n".join(b["text"] for b in blocks)
        # D-09 active roster — must all 6 names appear verbatim
        for name in (
            "Roibu Valeria",
            "Raileanu Leon",
            "Godja Adina Maria",
            "Dragoi Mihaela",
            "Zagrian Emilia",
            "Moaca Andreea",
        ):
            assert name in text, f"Missing salesperson name: {name}"

    def test_pb4_mvp1_data_limits_block(self) -> None:
        from app.services.chat.prompt_builder import (
            _build_tenant_facts,
            build_system_prompt,
        )

        blocks = build_system_prompt(_build_tenant_facts())
        text = "\n".join(b["text"] for b in blocks)
        # CHAT-05 MVP1 data limits — phrases per plan acceptance
        assert "estimated_value" in text
        assert "Nu am acces" in text or "Nu ai acces" in text
        assert "Meta" in text
        assert "Google" in text
        assert "TikTok" in text
        assert "GA4" in text
        assert "Search Console" in text or "GSC" in text

    def test_pb5_three_showrooms(self) -> None:
        from app.services.chat.prompt_builder import (
            _build_tenant_facts,
            build_system_prompt,
        )

        blocks = build_system_prompt(_build_tenant_facts())
        text = "\n".join(b["text"] for b in blocks)
        # Sofa Belle showrooms
        assert "Brașov" in text
        assert "București" in text
        assert "Cluj-Napoca" in text

    def test_pb6_markdown_link_format_documented(self) -> None:
        from app.services.chat.prompt_builder import (
            _build_tenant_facts,
            build_system_prompt,
        )

        blocks = build_system_prompt(_build_tenant_facts())
        text = "\n".join(b["text"] for b in blocks)
        # D-18: markdown link [Label](/sales) format documented
        # accept either the literal token "[" + "(/sales" anywhere in the prompt
        assert "/sales" in text
        assert "Markdown" in text or "markdown" in text

    def test_tenant_facts_helper_shape(self) -> None:
        from app.services.chat.prompt_builder import _build_tenant_facts

        facts = _build_tenant_facts()
        assert facts["tenant_name"] == "Sofa Belle"
        assert isinstance(facts["showrooms"], list)
        assert len(facts["showrooms"]) == 3
        assert len(facts["salesperson_roster"]) == 6
