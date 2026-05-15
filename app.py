import os
import json
import urllib.request
from collections import deque
from flask import Flask, request, jsonify

app = Flask(__name__)

ZAPI_URL = "https://api.z-api.io/instances/3F30FB803D590062508E8E0A56E81C5F/token/AC88481F2EFB9129AB772C52/send-text"
ZAPI_TOKEN = "F6f2fd019bcfe4b0ba62e819a6b5f92b8S"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

LEADS = {
    "5511973865074": {
        "nome": "Nido",
        "empresa": "Revista Nova Família",
        "segmento": "publicação/conteúdo",
        "dores": "automação de conteúdo, YouTube, Instagram, captação de clientes",
        "estagio": "reunião realizada",
    },
    "5511988877083": {
        "nome": "Alex",
        "empresa": "",
        "segmento": "",
        "dores": "",
        "estagio": "reunião agendada",
    },
    "5583999932535": {
        "nome": "Adão",
        "empresa": "",
        "segmento": "",
        "dores": "",
        "estagio": "reunião agendada",
    },
    "5521991901906": {
        "nome": "Amanda",
        "empresa": "Amanda Alves Advocacia",
        "segmento": "jurídico",
        "dores": "CRM, automação de pré-vendas, produtividade",
        "estagio": "follow-up pós grupo",
    },
    "5519995957469": {
        "nome": "Juliana",
        "empresa": "Sevenlab Ambiental",
        "segmento": "serviços ambientais",
        "dores": "automação de processos, captação",
        "estagio": "follow-up pós grupo",
    },
    "5521964421086": {
        "nome": "Giovanni",
        "empresa": "Braceg",
        "segmento": "segurança contra incêndio",
        "dores": "prospecção ativa, integração de propostas e orçamentos",
        "estagio": "morno - aguardando resposta",
    },
    "5511973187373": {
        "nome": "David",
        "empresa": "",
        "segmento": "",
        "dores": "",
        "estagio": "morno - aguardando resposta",
    },
}

# Histórico de conversa por número (mantém os últimos 20 turnos = 10 trocas)
HISTORICO = {}

SYSTEM_PROMPT = """Você é a assistente de vendas da Agatha Teles, Closer da Viver de IA.
Responda mensagens de WhatsApp de leads em negociação de forma personalizada, estratégica e humanizada.

Diretrizes:
- Tom leve, próximo, sem formalidade excessiva
- Nunca mencione que é uma IA ou automação
- Use metodologia de venda desafiadora: gere insight, desafie o status quo do lead
- Foco em avançar o lead para reunião individual ou fechamento
- Mensagens curtas (máximo 3 parágrafos)
- Sem travessão, sem bullet points longos
- Assine sempre como Agatha
- Leve em conta todo o histórico da conversa para manter contexto e continuidade natural

Se o lead perguntar sobre reagendamento, ofereça disponibilidade e peça para confirmar.
Se demonstrar interesse, direcione para o próximo passo (reunião ou proposta).
Se tiver objeção, acolha e redirecione com case ou insight relevante.
Se for um lead desconhecido, trate como novo contato interessado em automação e IA para negócios."""


def gerar_resposta(mensagem: str, lead: dict, historico: list) -> str:
    contexto = (
        f"Lead: {lead.get('nome') or 'Lead'}\n"
        f"Empresa: {lead.get('empresa') or 'não informada'}\n"
        f"Segmento: {lead.get('segmento') or 'não informado'}\n"
        f"Dores mapeadas: {lead.get('dores') or 'não mapeadas'}\n"
        f"Estágio no pipeline: {lead.get('estagio') or 'novo contato'}"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Contexto do lead:\n{contexto}"},
    ]
    messages.extend(historico)
    messages.append({"role": "user", "content": mensagem})

    payload = {
        "model": "llama3-8b-8192",
        "messages": messages,
        "max_tokens": 400,
        "temperature": 0.7,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(GROQ_URL, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {GROQ_API_KEY}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"].strip()


def enviar_whatsapp(phone: str, message: str):
    payload = {"phone": phone, "message": message}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(ZAPI_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("client-token", ZAPI_TOKEN)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True, silent=True) or {}

    phone = data.get("phone") or data.get("from", "")
    texto = (
        data.get("text", {}).get("message", "")
        or data.get("message", "")
    )

    if not phone or not texto:
        return jsonify({"status": "ignored"}), 200
    if data.get("fromMe") or data.get("isGroup"):
        return jsonify({"status": "ignored"}), 200

    phone_clean = phone.replace("+", "").replace("-", "").replace(" ", "")

    lead = LEADS.get(phone_clean, {
        "nome": "Lead",
        "empresa": "",
        "segmento": "",
        "dores": "",
        "estagio": "novo contato",
    })

    if phone_clean not in HISTORICO:
        HISTORICO[phone_clean] = deque(maxlen=20)

    historico_atual = list(HISTORICO[phone_clean])

    try:
        resposta = gerar_resposta(texto, lead, historico_atual)
        HISTORICO[phone_clean].append({"role": "user", "content": texto})
        HISTORICO[phone_clean].append({"role": "assistant", "content": resposta})
        enviar_whatsapp(phone_clean, resposta)
        return jsonify({"status": "sent", "to": phone_clean}), 200
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
