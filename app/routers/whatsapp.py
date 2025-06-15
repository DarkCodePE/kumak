import logging
import os
import traceback
from typing import Dict, Any
import httpx
from fastapi import APIRouter, Request, Response

# Importar tu servicio existente
from app.services.chat_service import process_message

logger = logging.getLogger(__name__)

# Router para WhatsApp
whatsapp_router = APIRouter(
    prefix="/whatsapp",
    tags=["whatsapp"],
)

# Credenciales de WhatsApp API
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")

# Diccionario para trackear threads activos con interrupts
active_interrupts = {}


@whatsapp_router.api_route("/webhook", methods=["GET", "POST"])
async def whatsapp_webhook(request: Request) -> Response:
    """Webhook para manejar mensajes de WhatsApp."""

    if request.method == "GET":
        # Verificación del webhook
        params = request.query_params

        if params.get("hub.verify_token") == WHATSAPP_VERIFY_TOKEN:
            challenge = params.get("hub.challenge")
            logger.info("Webhook verificado exitosamente")
            return Response(content=challenge, status_code=200)
        else:
            logger.warning("Token de verificación incorrecto")
            return Response(content="Token de verificación incorrecto", status_code=403)

    # Manejar POST (mensajes entrantes)
    try:
        data = await request.json()
        logger.info(f"Webhook recibido: {data}")

        # Verificar estructura de datos
        if "entry" not in data or not data["entry"]:
            return Response(content="Estructura de datos inválida", status_code=400)

        entry = data["entry"][0]
        if "changes" not in entry or not entry["changes"]:
            return Response(content="No hay cambios en el webhook", status_code=200)

        change = entry["changes"][0]
        if "value" not in change:
            return Response(content="Valor faltante en webhook", status_code=400)

        value = change["value"]

        # Procesar mensajes
        if "messages" in value and value["messages"]:
            await handle_incoming_message(value["messages"][0])
            return Response(content="Mensaje procesado", status_code=200)

        # Procesar actualizaciones de estado
        elif "statuses" in value:
            logger.info("Actualización de estado recibida")
            return Response(content="Estado actualizado", status_code=200)

        else:
            logger.warning("Tipo de webhook no reconocido")
            return Response(content="Tipo de evento desconocido", status_code=400)

    except Exception as e:
        logger.error(f"Error procesando webhook: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return Response(content="Error interno del servidor", status_code=500)


async def handle_incoming_message(message_data: Dict[str, Any]) -> None:
    """Maneja un mensaje entrante de WhatsApp."""
    try:
        from_number = message_data["from"]
        message_type = message_data["type"]

        # Procesar mensajes de texto y respuestas de botones
        if message_type == "text":
            user_message = message_data["text"]["body"]
        elif message_type == "interactive":
            # Manejar respuestas de botones
            interactive_data = message_data["interactive"]
            if interactive_data["type"] == "button_reply":
                button_title = interactive_data["button_reply"]["title"]
                button_id = interactive_data["button_reply"]["id"]
                
                # Convertir respuestas de botones a texto más natural
                if button_id.startswith("sector_"):
                    sector_map = {
                        "sector_restaurant": "Restaurante",
                        "sector_retail": "Retail/Comercio",
                        "sector_services": "Servicios profesionales"
                    }
                    user_message = sector_map.get(button_id, button_title)
                elif button_id.startswith("location_"):
                    location_map = {
                        "location_local": "Tengo un local físico",
                        "location_online": "Opero completamente online",
                        "location_both": "Tengo local físico y también vendo online"
                    }
                    user_message = location_map.get(button_id, button_title)
                else:
                    user_message = button_title
            else:
                user_message = "Respuesta interactiva recibida"
        else:
            await send_whatsapp_message(
                from_number,
                "Por favor envía tu mensaje como texto o usa los botones disponibles. Estoy aquí para ayudarte a desarrollar propuestas de crecimiento para tu PYME 🚀"
            )
            return
        thread_id = f"whatsapp_{from_number}"

        logger.info(f"Procesando mensaje de {from_number}: {user_message}")

        # Verificar si este thread tiene un interrupt activo
        is_resuming = thread_id in active_interrupts

        if is_resuming:
            logger.info(f"Resumiendo conversación interrumpida para {thread_id}")
            # Remover del diccionario de interrupts activos
            del active_interrupts[thread_id]

        # Usar tu servicio existente
        result = process_message(
            message=user_message,
            thread_id=thread_id,
            is_resuming=is_resuming
        )

        await handle_chat_result(from_number, thread_id, result, user_message)

    except Exception as e:
        logger.error(f"Error manejando mensaje entrante: {str(e)}")
        await send_whatsapp_message(
            from_number,
            "Disculpa, encontré un problema procesando tu mensaje. ¿Podrías intentar nuevamente?"
        )


def create_sector_buttons():
    """Crea botones para selección de sector."""
    return [
        {"type": "reply", "reply": {"id": "sector_restaurant", "title": "🍽️ Restaurante"}},
        {"type": "reply", "reply": {"id": "sector_retail", "title": "🛍️ Retail"}},
        {"type": "reply", "reply": {"id": "sector_services", "title": "💼 Servicios"}}
    ]

def create_location_buttons():
    """Crea botones para selección de ubicación."""
    return [
        {"type": "reply", "reply": {"id": "location_local", "title": "🏪 Local físico"}},
        {"type": "reply", "reply": {"id": "location_online", "title": "💻 Online"}},
        {"type": "reply", "reply": {"id": "location_both", "title": "🏪💻 Ambos"}}
    ]

def get_buttons_for_question(question: str):
    """Determina qué botones mostrar según la pregunta."""
    question_lower = question.lower()
    
    # Detectar preguntas sobre sector/industria
    sector_keywords = ["sector", "industria", "opera tu negocio", "tipo de negocio", "rubro"]
    if any(keyword in question_lower for keyword in sector_keywords):
        return create_sector_buttons()
    
    # Detectar preguntas sobre ubicación
    location_keywords = ["dónde opera", "ubicación", "donde opera", "opera principalmente"]
    if any(keyword in question_lower for keyword in location_keywords):
        return create_location_buttons()
    
    return None

async def handle_chat_result(from_number: str, thread_id: str, result: Dict[str, Any], original_message: str) -> None:
    """Maneja el resultado del procesamiento del chat."""
    try:
        if result["status"] == "completed":
            # Conversación completada normalmente
            response_text = result["answer"]
            buttons = get_buttons_for_question(response_text)
            
            success = await send_whatsapp_message(from_number, response_text, buttons)
            if success:
                logger.info(f"Respuesta enviada exitosamente a {from_number}")
            else:
                logger.error(f"Error enviando respuesta a {from_number}")

        elif result["status"] == "interrupted":
            # La conversación está esperando input humano
            logger.info(f"Conversación interrumpida para {thread_id}")

            # Agregar a threads activos con interrupt
            active_interrupts[thread_id] = {
                "timestamp": traceback.format_exc(),
                "last_message": original_message
            }

            # Enviar la respuesta del assistant + mensaje de interrupt
            response_text = result["answer"]

            # Agregar mensaje de instrucción para el usuario
            if result.get("interrupt_message"):
                response_text += f"\n\n{result['interrupt_message']}"
            else:
                response_text += "\n\n💬 Continúa la conversación o escribe 'done' para finalizar."

            # Determinar si necesita botones
            buttons = get_buttons_for_question(response_text)
            
            success = await send_whatsapp_message(from_number, response_text, buttons)
            if success:
                logger.info(f"Mensaje de interrupt enviado a {from_number}")
            else:
                logger.error(f"Error enviando mensaje de interrupt a {from_number}")

        else:
            # Error en el procesamiento
            logger.error(f"Error en resultado del chat: {result.get('error', 'Unknown error')}")
            await send_whatsapp_message(
                from_number,
                "Disculpa, encontré un problema procesando tu consulta. ¿Podrías intentar reformular tu pregunta?"
            )

    except Exception as e:
        logger.error(f"Error manejando resultado del chat: {str(e)}")
        await send_whatsapp_message(
            from_number,
            "Disculpa, encontré un problema técnico. Inténtalo nuevamente en unos momentos."
        )


async def send_whatsapp_message(phone_number: str, message: str, buttons: list = None) -> bool:
    """Envía un mensaje de WhatsApp con botones opcionales."""
    try:
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }

        # Truncar mensaje si es muy largo (WhatsApp tiene límites)
        if len(message) > 4096:
            message = message[:4090] + "..."

        # Si hay botones, usar mensaje interactivo
        if buttons and len(buttons) <= 3:  # WhatsApp permite máximo 3 botones
            payload = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": message},
                    "action": {
                        "buttons": buttons
                    }
                }
            }
        else:
            # Mensaje de texto normal
            payload = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "text",
                "text": {"body": message}
            }

        url = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                logger.info(f"Mensaje enviado exitosamente a {phone_number}")
                return True
            else:
                logger.error(f"Error enviando WhatsApp: {response.status_code} - {response.text}")
                return False

    except Exception as e:
        logger.error(f"Excepción enviando mensaje WhatsApp: {str(e)}")
        return False


@whatsapp_router.get("/active-interrupts")
async def get_active_interrupts():
    """Endpoint para debugging - ver threads con interrupts activos."""
    return {
        "active_interrupts": len(active_interrupts),
        "threads": list(active_interrupts.keys())
    }