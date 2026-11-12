# Policy retrieval eval (32 questions scored for recall)

| Method | Recall@5 | Recall@8 | MRR | Version questions | Exact-code recall@5 |
| --- | --- | --- | --- | --- | --- |
| bm25 | 0.92 | 0.97 | 0.83 | 5/5 | 1.00 |
| vector | 0.91 | 0.95 | 0.78 | 5/5 | 0.67 |
| hybrid | 0.97 | 1.00 | 0.85 | 5/5 | 1.00 |
| hybrid+xrefs | 0.97 | 1.00 | 0.85 | 5/5 | 1.00 |

Recall@8 by question type:

| Type | bm25 | vector | hybrid | hybrid+xrefs |
| --- | --- | --- | --- | --- |
| change_history | 1.00 | 1.00 | 1.00 | 1.00 |
| cross_document | 1.00 | 1.00 | 1.00 | 1.00 |
| cross_reference | 1.00 | 1.00 | 1.00 | 1.00 |
| exact_code | 1.00 | 1.00 | 1.00 | 1.00 |
| multi_clause | 0.50 | 0.75 | 1.00 | 1.00 |
| numeric | 1.00 | 1.00 | 1.00 | 1.00 |
| semantic | 1.00 | 1.00 | 1.00 | 1.00 |
| synonym | 1.00 | 1.00 | 1.00 | 1.00 |
| table_lookup | 1.00 | 0.00 | 1.00 | 1.00 |
| version | 1.00 | 1.00 | 1.00 | 1.00 |

Targets (hybrid): recall@8 >= 0.9 (1.00); version questions all right (5/5); exact-code recall@5 = 1.0 (1.00).
