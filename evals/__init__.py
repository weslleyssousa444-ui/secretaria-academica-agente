"""A suíte de avaliação do sistema de triagem (Parte 3, docs/evals.md).

    python -m evals.rodar --rotulo B --run 1                 # roda o dataset sobre o sistema entregue
    python -m evals.rodar --rotulo A --run 1 --ref parte-2   # o mesmo, sobre o código de uma versão anterior
    python -m evals.comparar evals/resultados/<A> evals/resultados/<B>
    python -m evals.metricas evals/resultados/<B>/traces.jsonl
"""
