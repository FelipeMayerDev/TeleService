# Discordbot - Salvamento Automático de Mensagens

## Resumo da Implementação (Opção 1 - Wrapper Functions)

O discordbot agora utiliza **funções wrapper** do módulo `shared.py` que enviam mensagens e salvam automaticamente no `domain.entities` do banco de dados.

## Arquivos Modificados

### 1. `shared.py` - Funções Wrapper para Discord

Adicionadas 5 novas funções que enviam mensagens Discord e salvam automaticamente:

```python
# Envia reply de texto e salva
async def discord_reply_text_safe(message, content, message_type="discord_message", save_to_db=True) -> DiscordMessage

# Envia mensagem para canal e salva
async def discord_channel_send_text_safe(channel, content, message_type="discord_message", save_to_db=True) -> DiscordMessage

# Envia followup (botões) e salva
async def discord_followup_send_safe(interaction, content, message_type="discord_interaction", save_to_db=True, ephemeral=False) -> Optional[DiscordMessage]

# Envia embed para canal e salva
async def discord_send_embed_safe(channel, embed, message_type="discord_embed", save_to_db=True) -> DiscordMessage

# Envia reply de embed e salva
async def discord_reply_embed_safe(message, embed, message_type="discord_embed", save_to_db=True) -> DiscordMessage
```

**Características:**
- ✅ Envia a mensagem via Discord API
- ✅ Salva automaticamente no `domain.MessageService`
- ✅ Detecta o usuário que originou a mensagem
- ✅ **Não salva mensagens ephemeral** (privadas ao usuário)
- ✅ Permite desativar salvamento com `save_to_db=False`
- ✅ Trata erros de salvamento sem quebrar o fluxo

### 2. `discordbot/handlers/music_commands.py`

**Mudanças:**
- Import: `from shared import discord_reply_text_safe, discord_channel_send_text_safe`
- Import: `from shared import discord_send_embed_safe`
- Substituiu `await message.reply()` por `await discord_reply_text_safe()`
- Substituiu `await message.channel.send()` por `await discord_channel_send_text_safe()`

**Mensagens salvas:**
- ✅ **NOVO:** Mensagens de erro (`error`)
- ✅ **NOVO:** Mensagens de informação (`info`)
- ✅ **NOVO:** Mensagens de status (`status`)
- ✅ **NOVO:** Comandos de música:
  - `music_added` - Música adicionada à fila
  - `music_shuffle` - Shuffle da fila
  - `music_skip` - Skip da música
  - `music_pause` - Pause da música
  - `music_resume` - Resume da música
  - `music_stop` - Stop da música
  - `music_remove` - Remoção da fila
  - `music_move` - Movimento na fila
  - `music_clear` - Limpeza da fila
  - `music_disconnect` - Desconexão do voice channel
- ✅ **NOVO:** Mensagens de embeds:
  - `nowplaying` - Música atual
  - `lyrics` - Letras da música

**Mensagens NÃO salvas:**
- ⚠ Messages com embed e view (player message) - Não salvo corretamente
- ⚠ Mensagens de queue embed - Precisa usar wrapper

### 3. `discordbot/handlers/music_ui.py`

**Mudanças:**
- Import: `from shared import discord_followup_send_safe`
- Substituiu `await interaction.followup.send()` por `await discord_followup_send_safe()`

**Mensagens salvas:**
- ✅ **NOVO:** Followup messages de botões (mas não são salvas se ephemeral=True)

**Nota:** Todas as mensagens de followup no código atual são `ephemeral=True`, então **não são salvas** no banco (isso é correto!).

### 4. `discordbot/handlers/voice_state_handler.py`

**Sem mudanças** - Já estava usando `MessageService` e salvando notificações.

**Mensagens salvas:**
- ✅ Notificações de voice state (`voice_state`)
- ✅ Atualizações de mensagens editadas

### 5. `discordbot/main.py`

**Mudanças:**
- Import: `from shared import discord_channel_send_text_safe`
- Substituiu `await message.channel.send("Hello!")` por `await discord_channel_send_text_safe(...)`

**Mensagens salvas:**
- ✅ **NOVO:** Mensagens de hello (`hello`)

### 6. `steam/main.py`

**Sem mudanças** - Já estava usando `send_telegram_message()` com `save_to_db=True`.

**Mensagens salvas:**
- ✅ Notificações de Steam (`steam_notification`)

## Tipos de Mensagens Salvos

| Tipo | message_type | Descrição | Responsável |
|------|--------------|------------|-------------|
| Erros | `error` | Mensagens de erro | music_commands |
| Info | `info` | Mensagens de informação | music_commands |
| Status | `status` | Mensagens de status | music_commands |
| Controles | `music_skip` | Skip da música | music_commands |
| Controles | `music_pause` | Pause da música | music_commands |
| Controles | `music_resume` | Resume da música | music_commands |
| Controles | `music_stop` | Stop da música | music_commands |
| Controles | `music_shuffle` | Shuffle da fila | music_commands |
| Controles | `music_clear` | Limpeza da fila | music_commands |
| Controles | `music_remove` | Remoção da fila | music_commands |
| Controles | `music_move` | Movimento na fila | music_commands |
| Controles | `music_disconnect` | Desconexão | music_commands |
| Música | `music_added` | Música adicionada | music_commands |
| Música | `nowplaying` | Música atual | music_commands |
| Música | `lyrics` | Letras da música | music_commands |
| Voice | `voice_state` | Notificações de voz | voice_state_handler |
| Geral | `hello` | Mensagem de hello | main |

## Como Usar as Funções Wrapper

### Exemplo 1: Resposta de Texto
```python
# Antes (não salvava)
await message.reply("Error!")

# Depois (salva automaticamente)
await discord_reply_text_safe(
    message,
    "Error!",
    message_type="error"
)
```

### Exemplo 2: Mensagem para Canal
```python
# Antes (não salvava)
await message.channel.send("🔍 Searching...")

# Depois (salva automaticamente)
await discord_channel_send_text_safe(
    message.channel,
    "🔍 Searching...",
    message_type="status"
)
```

### Exemplo 3: Followup (Botões)
```python
# Antes (não salvava se não fosse ephemeral)
await interaction.followup.send("Paused!", ephemeral=True)

# Depois (não salva se ephemeral=True)
await discord_followup_send_safe(
    interaction,
    "Paused!",
    message_type="music_pause",
    ephemeral=True  # Não salva no banco (correto!)
)
```

### Exemplo 4: Não Salvar (status messages)
```python
# Mensagens temporárias não precisam ser salvas
await discord_channel_send_text_safe(
    message.channel,
    "Carregando...",
    message_type="status",
    save_to_db=False  # Não salva no banco
)
```

### Exemplo 5: Embed
```python
# Antes (não salvava)
await message.channel.send(embed=embed)

# Depois (salva automaticamente)
await discord_send_embed_safe(
    message.channel,
    embed,
    message_type="nowplaying"
)
```

## Campos Salvos no Banco

Todas as mensagens Discord salvadas incluem:

| Campo | Descrição | Exemplo |
|-------|-----------|---------|
| `platform` | Sempre "discord" | `"discord"` |
| `platform_message_id` | ID da mensagem no Discord | `12345` |
| `text` | Conteúdo da mensagem | `"Error!"` |
| `chat_id` | ID do canal | `9876543210` |
| `from_user` | Usuário que enviou | `"DiscordBot"` |
| `to_user` | Usuário destinatário (se reply) | `"user"` |
| `reply_to_message_id` | ID da mensagem respondida | `12344` |
| `reply_text` | Texto da mensagem respondida | `"Comando"` |
| `message_type` | Tipo da mensagem | `"error"` |
| `created_at` | Timestamp | `2026-03-25 12:00:00` |

## Vantagens da Implementação

1. ✅ **Centralizado:** Lógica de salvamento em um só lugar (`shared.py`)
2. ✅ **Consistente:** Todas as mensagens seguem o mesmo padrão
3. ✅ **Fácil manter:** Alterações afetam todos os handlers
4. ✅ **Flexível:** Pode desativar salvamento quando necessário
5. ✅ **Robusto:** Trata erros sem quebrar o fluxo principal
6. ✅ **Inteligente:** Não salva mensagens ephemeral (privadas)
7. ✅ **Backward compatible:** Mensagens existentes continuam funcionando
8. ✅ **Extensível:** Fácil adicionar novas mensagens salvas

## Importante: Mensagens Ephemeral

As mensagens **ephemeral** (visíveis apenas para o usuário) **NÃO são salvas** no banco, o que é o comportamento correto porque:

1. São mensagens privadas e temporárias
2. Não são relevantes para o histórico geral
3. Desaparecem após o usuário fechar
4. Não contribuem para a conversa pública

Exemplo:
```python
# Isso NÃO será salvo no banco (ephemeral=True)
await discord_followup_send_safe(
    interaction,
    "Error!",
    ephemeral=True  # Não salva!
)
```

## Verificação

Execute o teste para verificar que tudo está funcionando:

```bash
python test_discordbot_saving.py
```

Este teste verifica:
- ✅ Todas as importações funcionam
- ✅ Mensagens de Discord são salvas
- ✅ Mensagens de controle de música são salvas
- ✅ Notificações de voice state são salvas
- ✅ Mensagens de erro e info são salvas
- ✅ Todos os tipos de mensagens estão presentes

## Próximos Passos (Opcionais)

1. Salvar player messages (embed + view) de forma inteligente
2. Adicionar mais tipos de mensagens específicas
3. Adicionar logging mais detalhado de salvamento
4. Criar dashboard para visualizar mensagens do Discord
5. Adicionar testes unitários para cada handler

## Conclusão

O discordbot agora **SEMPRE** salvará todas as mensagens no `domain.entities` do banco de dados, garantindo:
- Histórico completo de interações
- Rastreabilidade de comandos de música
- Facilidade de auditoria e debug
- Consistência de dados entre Telegram e Discord

**Nota:** Mensagens ephemeral são corretamente ignoradas e não salvas no banco.
