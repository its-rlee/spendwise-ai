"""Apply Week 3 Day 5 integration edits to an existing SpendWise clone.

Run from repository root: python apply_day05.py
New files in backend/app and backend/tests are supplied with the ZIP.
Safe to rerun; aborts on unexpected upstream changes instead of guessing.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def replace(path: str, old: str, new: str) -> None:
    file = ROOT / path
    source = file.read_text(encoding="utf-8")
    if new in source:
        print("Already applied:", path)
        return
    if source.count(old) != 1:
        raise RuntimeError(f"Expected one patch location in {path}; found {source.count(old)}. Don't overwrite upstream code.")
    file.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("Patched:", path)


def add_after(path: str, marker: str, new_line: str) -> None:
    replace(path, marker, marker + new_line)


def main():
    for path in ("backend/app/category_service.py", "backend/app/category_router.py", "backend/tests/test_category_predictions.py"):
        if not (ROOT / path).exists():
            raise SystemExit(f"ZIP not extracted correctly; missing {path}")

    add_after("backend/app/main.py", "from .health import router as health_router\n",
              "from .category_router import router as category_router\n")
    add_after("backend/app/main.py", "app.include_router(health_router)\n",
              "app.include_router(category_router)\n")

    path = ROOT / "backend/requirements.txt"
    lines = path.read_text(encoding="utf-8").splitlines()
    for dep in ("scikit-learn==1.9.1", "joblib>=1.5,<2"):
        if dep not in lines:
            lines.append(dep)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Updated: backend/requirements.txt")

    path = ROOT / ".gitignore"
    text = path.read_text(encoding="utf-8")
    ignore = "\n# Locally trained model (not a source artifact)\nbackend/ml_models/\n"
    if "backend/ml_models/" not in text:
        path.write_text(text.rstrip() + "\n" + ignore, encoding="utf-8")
    (ROOT / "backend/ml_models").mkdir(exist_ok=True)

    replace("compose.yaml",
            "      TESSERACT_CMD: /usr/bin/tesseract\n",
            "      TESSERACT_CMD: /usr/bin/tesseract\n"
            "      ML_MODEL_PATH: /app/ml_models/receipt_category_model.joblib\n"
            "      ML_OLLAMA_FALLBACK: ${ML_OLLAMA_FALLBACK:-false}\n"
            "      ML_CATEGORY_THRESHOLD: ${ML_CATEGORY_THRESHOLD:-0.55}\n")
    replace("compose.yaml",
            "    volumes:\n      - type: bind\n        source: ${USERPROFILE}/.aws\n",
            "    volumes:\n      - type: bind\n        source: ./backend/ml_models\n        target: /app/ml_models\n        read_only: true\n      - type: bind\n        source: ${USERPROFILE}/.aws\n")

    replace("mobile/lib/services/spendwise_api.dart",
            "  void dispose() {\n",
            "  Future<List<Map<String, dynamic>>> suggestDraftCategories(String draftId) async {\n"
            "    final result = await _request(\n"
            "      '/api/v1/drafts/$draftId/category-suggestions',\n"
            "      body: <String, dynamic>{},\n"
            "    );\n"
            "    final rows = (result as Map<String, dynamic>)['suggestions'] as List;\n"
            "    return rows.map((row) => Map<String, dynamic>.from(row as Map)).toList();\n"
            "  }\n\n"
            "  void dispose() {\n")

    replace("mobile/lib/screens/receipt_items_editor.dart",
            "  _ItemFields([ReceiptItemDraft? item])\n",
            "  _ItemFields([ReceiptItemDraft? item, String? suggestedCategory])\n")
    replace("mobile/lib/screens/receipt_items_editor.dart",
            "      category.text = item.category;\n",
            "      category.text = suggestedCategory ?? item.category;\n")
    replace("mobile/lib/screens/receipt_items_editor.dart",
            "  final List<ReceiptItemDraft> initialItems;\n\n  const ReceiptItemsEditor({super.key, required this.initialItems});",
            "  final List<ReceiptItemDraft> initialItems;\n"
            "  final Map<int, String> suggestedCategories;\n\n"
            "  const ReceiptItemsEditor({\n"
            "    super.key,\n"
            "    required this.initialItems,\n"
            "    this.suggestedCategories = const {},\n"
            "  });")
    replace("mobile/lib/screens/receipt_items_editor.dart",
            "    for (final item in widget.initialItems) {\n      _rows.add(_ItemFields(item));\n    }",
            "    for (var index = 0; index < widget.initialItems.length; index++) {\n"
            "      _rows.add(_ItemFields(widget.initialItems[index], widget.suggestedCategories[index]));\n"
            "    }")
    replace("mobile/lib/screens/receipt_items_editor.dart",
            "              'Correct mistakes before approval.',",
            "              'Correct mistakes before approval. AI category suggestions are unverified.',")

    replace("mobile/lib/screens/document_review_screen.dart",
            "  bool get _isReceipt {\n",
            "  Future<void> _suggestAndReview(TransactionDraftRecord draft) async {\n"
            "    await _run(() async {\n"
            "      final suggestions = await _api.suggestDraftCategories(draft.id);\n"
            "      if (!mounted) return;\n"
            "      final overrides = <int, String>{};\n"
            "      for (final suggestion in suggestions) {\n"
            "        final index = suggestion['line_index'];\n"
            "        final category = suggestion['category'];\n"
            "        if (index is int && category is String && category.isNotEmpty) {\n"
            "          overrides[index] = category;\n"
            "        }\n"
            "      }\n"
            "      final edited = await showDialog<List<Map<String, dynamic>>>(\n"
            "        context: context,\n"
            "        builder: (_) => ReceiptItemsEditor(\n"
            "          initialItems: draft.receiptItems,\n"
            "          suggestedCategories: overrides,\n"
            "        ),\n"
            "      );\n"
            "      if (edited == null || !mounted) return;\n"
            "      await _api.saveDraftItems(draft.id, edited);\n"
            "      await _fetchDrafts();\n"
            "    });\n"
            "  }\n\n"
            "  bool get _isReceipt {\n")
    replace("mobile/lib/screens/document_review_screen.dart",
            "                        if (draft.status == 'pending')\n                          Wrap(\n",
            "                        if (draft.status == 'pending' && _isReceipt)\n"
            "                          TextButton.icon(\n"
            "                            onPressed: _busy ? null : () => _suggestAndReview(draft),\n"
            "                            icon: const Icon(Icons.auto_fix_high),\n"
            "                            label: const Text('Suggest categories (ML/Ollama)'),\n"
            "                          ),\n\n"
            "                        if (draft.status == 'pending')\n                          Wrap(\n")
    print("\nDay 5 patches applied. Local model and Ollama configuration are next.")


if __name__ == "__main__":
    main()
