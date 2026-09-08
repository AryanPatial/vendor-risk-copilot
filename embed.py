from functools import lru_cache

from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384
BATCH_SIZE = 64


@lru_cache(maxsize=1)
def get_model():
    return SentenceTransformer(MODEL_NAME)


def embed_texts(texts):
    """Phase A: embed many stored texts at once."""
    return get_model().encode(
        texts,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > 200,
    )


def embed_query(text):
    """Phase B: embed one incoming question."""
    return get_model().encode(text, normalize_embeddings=True)


if __name__ == "__main__":
    vectors = embed_texts(["Do you encrypt data at rest?", "Are background checks performed?"])
    print(f"model      : {MODEL_NAME}")
    print(f"shape      : {vectors.shape}  (2 texts, {DIMENSIONS} numbers each)")
    print(f"length of first vector: {(vectors[0] @ vectors[0]) ** 0.5:.4f}  (normalised = 1.0)")
    print(f"first 6 numbers: {vectors[0][:6].round(4)}")
