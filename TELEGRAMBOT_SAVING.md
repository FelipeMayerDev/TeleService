# Telegrambot - Salvamento Automático de Mensagens

## Resumo da Implementação (Opção 1 - Wrapper Functions)

O telegrambot agora utiliza **funções wrapper** do módulo `shared.py` que enviam mensagens e salvam automaticamente no `domain.entities` do banco de dados.

## Arquivos Modificados

### 1. `shared.py` - Funções Wrapper

Adicionadas 5 novas funções que enviam mensagens e salvam automaticamente:

```python
# Envia mensagem de texto e salva
async def reply_text_safe(message, text, parse_mode=None, message_type="text", save_to_db=True) -> Message

# Envia foto e salva
async def reply_photo_safe(message, photo, caption=None, parse_mode=None, message_type="photo", save_to_db=True) -> Message

# Envia vídeo e salva
async def reply_video_safe(message, video, caption=None, parse_mode=None, message_type="video", save_to_db=True) -> Message

# Envia mensagem via bot e salva
async def send_message_safe(bot, chat_id, text, parse_mode=None, message_type="text", save_to_db=True) -> Optional[Message]

# Envia foto via bot e salva
async def send_photo_safe(bot, chat_id, photo, caption=None, parse_mode=None, message_type="photo", save_to_db=True) -> Optional[Message]
```

**Características:**
- ✅ Envia a mensagem via Telegram API
- ✅ Salva automaticamente no `domain.MessageService`
- ✅ Detecta o usuário que originou a mensagem
- ✅ Captura `reply_to_message_id` e `reply_text`
- ✅ Permite desativar salvamento com `save_to_db=False`
- ✅ Trata erros de salvamento sem quebrar o fluxo

### 2. `telegrambot/handlers/text.py`

**Mudanças:**
- Import: `from shared import reply_text_safe`
- Substituiu `await message.reply_text()` por `await reply_text_safe()`
- Tipo de mensagem: `ai_response` para respostas do bot

**Mensagens salvas:**
- ✅ Mensagens de texto de usuários (já era salvo)
- ✅ **NOVO:** Respostas do bot quando mencionado (`ai_response`)

### 3. `telegrambot/handlers/commands.py`

**Mudanças:**
- Import: `from shared import reply_text_safe, reply_photo_safe`
- Substituiu `await update.message.reply_text()` por `await reply_text_safe()`
- Substituiu `await update.message.reply_photo()` por `await reply_photo_safe()`

**Mensagens salvas:**
- ✅ **NOVO:** Mensagens de FAQ (`faq`)
- ✅ **NOVO:** Resumos de vídeo (`video_resume`)
- ✅ **NOVO:** Imagens de busca (`search_image`)
- ✅ **NOVO:** Mensagens de erro (`error`)

**Mensagens NÃO salvas:**
- ⚠ Status messages (ex: "Iniciando resumo...") - `save_to_db=False`
- ⚠ Messages deletadas automaticamente

### 4. `telegrambot/handlers/media.py`

**Mudanças:**
- Import: `from shared import reply_text_safe, reply_video_safe`
- Substituiu `await update.message.reply_text()` por `await reply_text_safe()`
- Substituiu `await update.message.reply_video()` por `await reply_video_safe()`

**Mensagens salvas:**
- ✅ **NOVO:** Vídeos enviados pelo bot em resposta a links (`media`)

**Mensagens NÃO salvas:**
- ⚠ Status messages - `save_to_db=False`
- ⚠ Messages deletadas automaticamente

### 5. `telegrambot/handlers/media_logger.py`

**Sem mudanças** - Já estava salvando todas as mensagens de mídia de usuários.

**Mensagens salvas:**
- ✅ Photos
- ✅ Videos
- ✅ Audio
- ✅ Documents
- ✅ Animations (GIFs)
- ✅ Locations
- ✅ Contacts
- ✅ Polls

### 6. `telegrambot/handlers/transcription.py`

**Sem mudanças** - Já estava salvando mensagens de voz.

**Mensagens salvas:**
- ✅ Voice messages
- ✅ Video notes

## Tipos de Mensagens Salvos

| Tipo | message_type | Descrição | Responsável |
|------|--------------|------------|-------------|
| Texto | `text` | Mensagens de texto de usuários | `text_handler` |
| Mídia | `photo` | Fotos | `media_logger` |
| Mídia | `video` | Vídeos | `media_logger` |
| Mídia | `audio` | Arquivos de áudio | `media_logger` |
| Mídia | `document` | Documentos | `media_logger` |
| Mídia | `animation` | GIFs | `media_logger` |
| Mídia | `location` | Localizações | `media_logger` |
| Mídia | `contact` | Contatos | `media_logger` |
| Mídia | `poll` | Enquetes | `media_logger` |
| Voz | `voice` | Mensagens de voz | `transcription_handler` |
| **IA** | `ai_response` | Respostas da IA | `text_handler` (NOVO!) |
| **FAQ** | `faq` | Mensagens de FAQ | `commands.faq` (NOVO!) |
| **Resumo** | `video_resume` | Resumos de vídeo | `commands.resume` (NOVO!) |
| **Busca** | `search_image` | Imagens de busca | `commands.search_image` (NOVO!) |
| **Mídia** | `media` | Vídeos enviados pelo bot | `media.get_media` (NOVO!) |

## Como Usar as Funções Wrapper

### Exemplo 1: Texto Simples
```python
# Antes (não salvava resposta do bot)
await message.reply_text("Olá!")

# Depois (salva automaticamente)
await reply_text_safe(message, "Olá!", message_type="text")
```

### Exemplo 2: Texto com Markdown
```python
# Antes
await message.reply_text("*Bold text*", parse_mode="markdown")

# Depois
await reply_text_safe(message, "*Bold text*", parse_mode="markdown", message_type="text")
```

### Exemplo 3: Foto
```python
# Antes
await message.reply_photo(photo, caption="Minha foto")

# Depois
await reply_photo_safe(message, photo, caption="Minha foto", message_type="photo")
```

### Exemplo 4: Vídeo
```python
# Antes
await message.reply_video(video, caption="Meu vídeo")

# Depois
await reply_video_safe(message, video, caption="Meu vídeo", message_type="video")
```

### Exemplo 5: Não Salvar (status messages)
```python
# Mensagens temporárias não precisam ser salvas
await reply_text_safe(
    message,
    "Carregando...",
    save_to_db=False  # Não salva no banco
)
```

## Campos Salvos no Banco

Todas as mensagens salvadas incluem:

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| `platform` | Sempre "telegram" | `"telegram"` |
| `platform_message_id` | ID da mensagem no Telegram | `12345` |
| `text` | Conteúdo da mensagem | `"Olá mundo"` |
| `chat_id` | ID do chat/grupo | `-1001234567890` |
| `from_user` | Usuário que enviou | `"username"` ou `"Bot"` |
| `to_user` | Usuário destinatário (se reply) | `"other_user"` |
| `reply_to_message_id` | ID da mensagem respondida | `12344` |
| `reply_text` | Texto da mensagem respondida | `"Pergunta original"` |
| `message_type` | Tipo da mensagem | `"ai_response"` |
| `created_at` | Timestamp | `2026-03-25 12:00:00` |

## Vantagens da Implementação

1. ✅ **Centralizado:** Lógica de salvamento em um só lugar (`shared.py`)
2. ✅ **Consistente:** Todas as mensagens seguem o mesmo padrão
3. ✅ **Fácil manter:** Alterações afetam todos os handlers
4. ✅ **Flexível:** Pode desativar salvamento quando necessário
5. ✅ **Robusto:** Trata erros sem quebrar o fluxo principal
6. ✅ **Backward compatible:** Mensagens de usuários continuam funcionando
7. ✅ **Extensível:** Fácil adicionar novas mensagens salvas

## Verificação

Execute o teste para verificar que tudo está funcionando:

```bash
python test_telegrambot_saving.py
```

Este teste verifica:
- ✅ Todas as importações funcionam
- ✅ Mensagens de usuários são salvas
- ✅ Respostas do bot são salvas
- ✅ Mensagens de FAQ são salvas
- ✅ Imagens de busca são salvas
- ✅ Vídeos são salvos
- ✅ Todos os tipos de mensagens estão presentes

## Próximos Passos (Opcionais)

1. Adicionar `edit_message_safe()` para mensagens editadas
2. Adicionar logging mais detalhado de salvamento
3. Adicionar estatísticas de mensagens salvas
4. Criar dashboard para visualizar mensagens
5. Adicionar testes unitários para cada handler

## Conclusão

O telegrambot agora **SEMPRE** salvará todas as mensagens no `domain.entities` do banco de dados, garantindo:
- Histórico completo de interações
- Rastreabilidade de respostas do bot
- Facilidade de auditoria e debug
- Consistência de dados entre Telegram e Discord
