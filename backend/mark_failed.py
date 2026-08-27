"""Mark a video document as "failed" after a workflow error.

Runs as a cleanup step that executes even when the main generation step
fails. It only flips documents that never finished (still "pending" or
"processing"), so it never clobbers a successful completed/posted result.
"""
import os
import sys

import firebase_store


def main() -> int:
    doc_id = (os.environ.get("DOCUMENT_ID") or "").strip()
    if not doc_id:
        print("No DOCUMENT_ID set; nothing to do.")
        return 0

    doc = firebase_store.get_document(doc_id)
    if not doc:
        print(f"Document {doc_id} not found; nothing to do.")
        return 0

    status = doc.get("status")
    if status in ("pending", "processing"):
        firebase_store.update_status(
            doc_id,
            "failed",
            error="Generation workflow failed before publishing.",
        )
        print(f"Marked {doc_id} as failed.")
    else:
        print(f"Document {doc_id} is '{status}'; leaving as is.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
