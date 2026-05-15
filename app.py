import os
import json
import urllib.request
from flask import Flask, request, jsonify
from anthropic import Anthropic

app = Flask(__name__)

ZAPI_URL = "https://api.z-api.io/instances/3F30FB803D590062508E8E0A56E81C5F/token/AC88481F2EFB9129AB772C52/send-text"
ZAPI_TOKEN = "F6f2fd019bcfe4b0ba62e819a6b5f92b8S"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Pipeline de leads â€” atualizar conforme necessÃ¡rio
LEADS = {
    "5511973865074": {
        "nome": "Nido Meireles",
        "empresa": "Revista Nova FamÃ­lia",
        "segmento": "publicaÃ§Ã£o/conteÃºdo",
        "dores": "automaÃ§Ã£o de conteÃºdo, YouTube, Instagram, captaÃ§Ã£o de clientes",
        "estagio": "reuniÃ£o realizada",
    },
    "5511988877083": {
        "nome": "Alex Saad",
        "empresa": "",
        "segmento": "",
        "dores": "",
        "estagio": "reuniÃ£o agendada",
    },
    "5583999932535": {
        "nome": "AdÃ£o GuimarÃ£es",
        "empresa": "",
        "segmento": "",
        "dores": "",
        "estagio": "reuniÃ£o agendada",
    },
    "5521991901906": {
        "nome": "Amanda Alves",
        "empresa": "Amanda Alves Advocacia",
        "segmento": "jurÃ­dico",
        "dores": "CRM, automaÃ§Ã£o de prÃ©-vendas, produtividade",
        "estagio": "follow-up pÃ³s grupo",
    },
    "5519995957469": {
        "nome": "Juliana Gomes",
        "empresa": "Sevenlab Ambiental",
        "segmento": "serviÃ§os ambientais",
        "dores": "automaÃ§Ã£o de processos, captaÃ§Ã£o",
        "estagio": "follow-up pÃ³s grupo",
    },
    "5521964421086": {
        "nome": "Giovanni Enrico",
        "empresa": "Braceg",
        "segmento": "seguranÃ§a contra incÃªndio",
        "dores": "prospecÃ§Ã£o ativa, integraÃ§Ã£o de propostas e orÃ§amentos",
        "estagio": "morno - aguardando resposta",
    },
    "5511973187373": {
        "nome": "David Moreno",
        "empresa": "",
        "segmento": "",
        "dores": "",
        "estagio": "morno - aguardando resposta",
    },
}

SYSTEM_PROMPT = """VocÃª Ã© a assistente de vendas da Agatha Teles, Closer da Viver de IA.
Responda mensagens de WhatsApp de leads em negociaÃ§Ã£o de forma personalizada, estratÃ©gica e humanizada.

Diretrizes:
- Tom leve, prÃ³ximo, sem formalidade excessiva
- Nunca mencione que Ã© uma IA ou automaÃ§Ã£o
- Use metodologia de venda desafiadora: gere insight, desafie o status quo do lead
- Foco em avanÃ§ar o lead para reuniÃ£o individual ou fechamento
- Mensagens curtas (mÃ¡x 3 parÃ¡grafos)
- Sem travessÃ£o, sem bullet points longos
- Assine sempre como Agatha

Se o lead perguntar sobre reagendamento, ofereÃ§a disponibilidade e peÃ§a para confirmar.
Se demonstrar interesse, direcione para o prÃ³ximo passo (reuniÃ£o ou proposta).
Se tiver objeÃ§Ã£o, acolha e redirecione com case ou insight relevante."""


def gerar_resposta(mensagem: str, lead: dict) -> str:
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    contexto = f"""
Lead: {lead.get('nome', 'desconhecido')}
Empresa: {lead.get('empresa', 'nÃ£o informada')}
Segmento: {lead.get('segmento', 'nÃ£o informado')}
Dores mapeadas: {lead.get('dores', 'nÃ£o mapeadas')}
EstÃ¡gio no pipeline: {lead.get('estagio', 'indefinido')}

Mensagem recebida: "{mensagem}"
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": contexto}],
    )
    return response.content[0].text


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

    # Z-API envia mensagens no campo "message" ou estrutura aninhada
    phone = data.get("phone") or data.get("from", "")
    texto = (
        data.get("text", {}).get("message", "")
        or data.get("message", "")
    )

    # Ignora mensagens vazias, de grupos ou enviadas por nÃ³s mesmos
    if not phone or not texto:
        return jsonify({"status": "ignored"}), 200
    if data.get("fromMe") or data.get("isGroup"):
        return jsonify({"status": "ignored"}), 200

    # Normaliza o nÃºmero
    phone_clean = phone.replace("+", "").replace("-", "").replace(" ", "")

    lead = LEADS.get(phone_clean, {
        "nome": "Lead",
        "empresa": "",
        "segmento": "",
        "dores": "",
        "estagio": "novo contato",
    })

    try:
        resposta = gerar_resposta(texto, lead)
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
