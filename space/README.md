---
title: Modelo para detecção de prompt injection
emoji: 🛡️
colorFrom: blue
colorTo: green
sdk: static
app_file: index.html
pinned: false
license: mit
short_description: Laboratório de classificação textual e segurança de IA
---

# Modelo para detecção de prompt injection

Estudo acadêmico independente de Daniel Kyochi sobre classificação de tentativas de prompt injection em português brasileiro.

Um modelo TF-IDF + regressão logística, treinado com dados sintéticos, analisa padrões de texto. A demonstração mostra o escore, contribuições dos termos, métricas e exemplos reais de erros do experimento.

**Não é um LLM nem uma proteção de produção.** O classificador apresenta falsos positivos e falsos negativos. Um resultado benigno não autoriza executar instruções.

[Modelo e metodologia](https://huggingface.co/kyochi-daniel/deteccao-prompt-injection) · [Código e treinamento](https://github.com/kyochi-daniel/deteccao-prompt-injection)

A inferência acontece no navegador. O texto não é enviado por esta aplicação, nem armazenado de forma persistente. A hospedagem pode registrar metadados normais de acesso conforme suas políticas. Este Space é estático, sem API de LLM nem hardware pago.
