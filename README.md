# Simulador de Rede de Filas

Trabalho prático de Avaliação de Desempenho / Simulação de Redes de Filas.

O projeto implementa um simulador baseado em eventos discretos para redes de filas com qualquer topologia, carregando o modelo a partir de um arquivo `.yml`.

## Arquivos

- `simulador.py`: código-fonte do simulador
- `modelo.yml`: arquivo com a configuração da rede de filas

## Modelo simulado

A rede possui 3 filas:

- `Q1`: G/G/1
- `Q2`: G/G/2/5
- `Q3`: G/G/2/10

A simulação começa com as filas vazias e o primeiro cliente chega no tempo `2.0`.

## Como executar

Para rodar o simulador, execute:

```bash
python3 simulador.py
```
