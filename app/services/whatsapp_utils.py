"""
Utilidades para WhatsApp - Manejo inteligente de mensajes largos y formateo
"""
import logging
from typing import List, Tuple
import tiktoken

logger = logging.getLogger(__name__)

# Límites para WhatsApp
WHATSAPP_MAX_LENGTH = 1024
WHATSAPP_OPTIMAL_LENGTH = 800  # Longitud óptima para mejor experiencia
MAX_TOKENS_PER_MESSAGE = 150   # Límite de tokens para respuestas

def count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """
    Cuenta los tokens en un texto usando tiktoken.
    
    Args:
        text: El texto a contar
        model: El modelo para el encoding (default: gpt-3.5-turbo)
    
    Returns:
        Número de tokens
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(f"Error contando tokens: {e}, usando estimación")
        # Estimación aproximada: 1 token ≈ 4 caracteres
        return len(text) // 4

def split_message_by_tokens(message: str, max_tokens: int = MAX_TOKENS_PER_MESSAGE) -> List[str]:
    """
    Divide un mensaje en partes basándose en límite de tokens.
    
    Args:
        message: El mensaje original
        max_tokens: Máximo de tokens por parte
    
    Returns:
        Lista de mensajes divididos
    """
    if count_tokens(message) <= max_tokens:
        return [message]
    
    # Dividir por párrafos primero
    paragraphs = message.split('\n\n')
    messages = []
    current_message = ""
    
    for paragraph in paragraphs:
        test_message = current_message + ("\n\n" if current_message else "") + paragraph
        
        if count_tokens(test_message) <= max_tokens:
            current_message = test_message
        else:
            # Si el mensaje actual no está vacío, guardarlo
            if current_message:
                messages.append(current_message.strip())
                current_message = paragraph
            
            # Si un párrafo individual es muy largo, dividirlo por oraciones
            if count_tokens(paragraph) > max_tokens:
                sentences = paragraph.split('. ')
                temp_message = ""
                
                for sentence in sentences:
                    test_sentence = temp_message + (". " if temp_message else "") + sentence
                    
                    if count_tokens(test_sentence) <= max_tokens:
                        temp_message = test_sentence
                    else:
                        if temp_message:
                            messages.append(temp_message.strip() + ".")
                        temp_message = sentence
                
                if temp_message:
                    current_message = temp_message
            else:
                current_message = paragraph
    
    if current_message:
        messages.append(current_message.strip())
    
    return messages

def format_business_response_for_whatsapp(message: str, max_tokens: int = MAX_TOKENS_PER_MESSAGE) -> str:
    """
    Formatea una respuesta empresarial para WhatsApp con límite de tokens.
    
    Args:
        message: El mensaje original
        max_tokens: Límite de tokens por mensaje
    
    Returns:
        Mensaje formateado o primer mensaje si es muy largo
    """
    if count_tokens(message) <= max_tokens:
        return message
    
    # Dividir en múltiples mensajes
    messages = split_message_by_tokens(message, max_tokens)
    
    if len(messages) == 1:
        return messages[0]
    
    # Retornar el primer mensaje con indicador
    first_message = messages[0]
    if not first_message.endswith('.'):
        first_message += "."
    
    first_message += f"\n\n📱 *Mensaje {1} de {len(messages)}*"
    return first_message

def get_continuation_messages(message: str, max_tokens: int = MAX_TOKENS_PER_MESSAGE) -> List[str]:
    """
    Obtiene los mensajes de continuación para un mensaje largo.
    
    Args:
        message: El mensaje original
        max_tokens: Límite de tokens por mensaje
    
    Returns:
        Lista de mensajes de continuación (sin el primero)
    """
    messages = split_message_by_tokens(message, max_tokens)
    
    if len(messages) <= 1:
        return []
    
    # Agregar numeración a los mensajes de continuación
    continuation_messages = []
    for i, msg in enumerate(messages[1:], 2):
        formatted_msg = msg
        if not formatted_msg.endswith('.'):
            formatted_msg += "."
        formatted_msg += f"\n\n📱 *Mensaje {i} de {len(messages)}*"
        continuation_messages.append(formatted_msg)
    
    return continuation_messages

def truncate_message_for_whatsapp(message: str, max_length: int = WHATSAPP_MAX_LENGTH) -> str:
    """
    Trunca un mensaje para que cumpla con los límites de WhatsApp (fallback).
    
    Args:
        message: El mensaje original
        max_length: Longitud máxima permitida
    
    Returns:
        Mensaje truncado con indicador si fue cortado
    """
    if len(message) <= max_length:
        return message
    
    # Reservar espacio para el indicador de truncado
    truncate_indicator = "\n\n... (mensaje truncado)"
    available_length = max_length - len(truncate_indicator)
    
    # Truncar en el último espacio o punto antes del límite
    truncated = message[:available_length]
    
    # Buscar el último punto o espacio para truncar de manera más natural
    last_period = truncated.rfind('.')
    last_space = truncated.rfind(' ')
    
    if last_period > available_length * 0.8:  # Si el punto está cerca del final
        truncated = truncated[:last_period + 1]
    elif last_space > available_length * 0.8:  # Si el espacio está cerca del final
        truncated = truncated[:last_space]
    
    return truncated + truncate_indicator

def log_message_stats(message: str, context: str = ""):
    """
    Registra estadísticas del mensaje para debugging.
    
    Args:
        message: El mensaje a analizar
        context: Contexto adicional para el log
    """
    char_count = len(message)
    token_count = count_tokens(message)
    
    logger.info(f"📊 Estadísticas del mensaje ({context}): "
               f"{char_count} chars, {token_count} tokens")
    
    if char_count > WHATSAPP_MAX_LENGTH:
        logger.warning(f"⚠️ Mensaje excede límite de WhatsApp: {char_count} > {WHATSAPP_MAX_LENGTH}")
    
    if token_count > MAX_TOKENS_PER_MESSAGE:
        logger.info(f"💡 Mensaje largo detectado: {token_count} tokens, "
                   f"se puede dividir en {len(split_message_by_tokens(message))} partes")

def create_smart_response_with_token_limit(prompt: str, max_tokens: int = MAX_TOKENS_PER_MESSAGE) -> str:
    """
    Crea un prompt que instruye al LLM a limitar su respuesta por tokens.
    
    Args:
        prompt: El prompt original
        max_tokens: Límite de tokens para la respuesta
    
    Returns:
        Prompt modificado con instrucciones de límite
    """
    token_instruction = f"""
IMPORTANTE: Tu respuesta debe ser concisa y no exceder {max_tokens} tokens (aproximadamente {max_tokens * 4} caracteres).
Si necesitas dar una respuesta más larga, enfócate en lo más importante y menciona que puedes dar más detalles si es necesario.

"""
    
    return token_instruction + prompt

# Función de compatibilidad con el código existente
def format_message_for_whatsapp(message: str) -> str:
    """Función de compatibilidad que usa el nuevo sistema de tokens."""
    return format_business_response_for_whatsapp(message) 