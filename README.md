# TKM Barbearia — App de Agendamento

App de agendamento real, rodando na sua própria máquina:
- **Backend:** Python (Flask + SQLite) — guarda os agendamentos e gera o QR code de verdade.
- **Frontend:** HTML/CSS/JavaScript — a telinha preta e dourada que o cliente usa.

## Como rodar

1. Instale o Python 3 (se ainda não tiver): https://www.python.org/downloads/
2. Abra um terminal na pasta `tkm-barbearia` e instale as dependências:
   ```
   pip install -r requirements.txt
   ```
3. Rode o servidor:
   ```
   python app.py
   ```
4. Abra no navegador: **http://127.0.0.1:5000**

Pronto — o app está no ar. Os dados ficam salvos no arquivo `tkm.db` (criado automaticamente na primeira execução), então os agendamentos continuam lá mesmo depois de fechar e abrir o servidor de novo.

## Regras já configuradas

- Atende de **7h às 18h**, em horários de 30 em 30 minutos.
- **Fechado** aos domingos e segundas.
- Corte **R$25** de terça a quarta, **R$65** de quinta a sábado.
- Cada agendamento gera um **código único de 6 caracteres** e um **QR code** (gerado em Python com a biblioteca `qrcode`), mostrado na confirmação e também disponível depois em "Meus Agendamentos" (buscando pelo WhatsApp usado).
- Não deixa marcar dois clientes no mesmo horário.

## Para deixar acessível pela internet (opcional)

Esse comando roda só na sua máquina (`127.0.0.1`). Para os clientes acessarem de fora, você precisa publicar em um servidor (ex: Render, Railway, PythonAnywhere) ou usar um serviço de túnel como o ngrok durante testes. Se quiser ajuda para publicar, é só pedir.

## Estrutura do projeto

```
tkm-barbearia/
├── app.py              → backend Python (Flask), banco SQLite, geração de QR code
├── requirements.txt    → dependências Python
├── templates/
│   └── index.html      → estrutura da página
└── static/
    ├── style.css        → visual preto e dourado
    └── script.js        → lógica do frontend (chama a API Python)
```
