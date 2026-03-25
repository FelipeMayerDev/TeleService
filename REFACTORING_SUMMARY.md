# Reestruturação do Banco de Dados - Domain Layer

## Resumo

O acesso ao banco de dados foi reestruturado seguindo os princípios de **Domain-Driven Design (DDD)**, tornando o banco um domínio central que pode ser usado tanto pelo bot do Telegram quanto pelo bot do Discord.

## Estrutura Antiga

```
database/
├── connection.py    # db = SqliteDatabase("database.sqlite")
├── models.py        # Feature, Message (com telegram_message_id)
├── managers.py      # FeatureManager, MessageManager (métodos estáticos)
└── main.py          # init_database()
```

**Problemas:**
- Managers eram classes estáticas (difícil testar)
- Model Message era específico do Telegram
- Acoplamento forte com bots
- Sem injeção de dependência
- Lógica de negócio misturada com acesso a dados

## Estrutura Nova

```
domain/
├── __init__.py              # Exports principais
├── models.py                # Modelos Peewee (camada de infraestrutura)
├── entities/                # Entidades de domínio
│   ├── __init__.py
│   ├── feature.py          # FeatureEntity
│   └── message.py          # MessageEntity
├── repositories/            # Camada de acesso a dados
│   ├── __init__.py
│   ├── base.py             # BaseRepository (genérico)
│   ├── feature_repository.py
│   └── message_repository.py
└── services/                 # Camada de lógica de negócio
    ├── __init__.py
    ├── feature_service.py
    └── message_service.py
```

## Arquivos Criados

### Entidades de Domínio
- `domain/entities/feature.py` - FeatureEntity com lógica de negócio
- `domain/entities/message.py` - MessageEntity (platform-agnostic)

### Repositories (Acesso a Dados)
- `domain/repositories/base.py` - BaseRepository genérico
- `domain/repositories/feature_repository.py` - FeatureRepository
- `domain/repositories/message_repository.py` - MessageRepository

### Services (Lógica de Negócio)
- `domain/services/feature_service.py` - FeatureService (casos de uso)
- `domain/services/message_service.py` - MessageService (casos de uso)

### Modelos e Configuração
- `domain/models.py` - Modelos Peewee + init_database com migrações
- `domain/__init__.py` - Export centralizado

## Migrações de Schema

### Tabela Message
```sql
-- Adicionou coluna platform
ALTER TABLE message ADD COLUMN platform TEXT DEFAULT 'telegram';

-- Renomeou telegram_message_id para platform_message_id
ALTER TABLE message RENAME COLUMN telegram_message_id TO platform_message_id;
```

## Arquivos Modificados

### Telegram Bot
- `telegrambot/main.py` - Usa `domain.init_database()`
- `telegrambot/handlers/text.py` - Usa `domain.MessageService`
- `telegrambot/handlers/media_logger.py` - Usa `domain.MessageService`
- `telegrambot/handlers/transcription.py` - Usa `domain.MessageService`

### Discord Bot
- `discordbot/main.py` - Usa `domain.init_database()`
- `discordbot/handlers/voice_state_handler.py` - Usa `domain.MessageService`

### Steam Monitor
- `steam/main.py` - Usa `domain.init_database()`

### Módulo Compartilhado
- `shared.py` - Usa `domain.MessageService`

## API do MessageService

### Métodos Disponíveis

```python
from domain import MessageService

service = MessageService()

# Adicionar mensagem (compatibilidade com Telegram)
service.add_telegram_message(
    telegram_message_id=123,
    text="Hello",
    chat_id=456,
    from_user="user",
    to_user=None,
    reply_to_message_id=None,
    reply_text=None,
    message_type="text",
)

# Adicionar mensagem (Discord)
service.add_discord_message(
    discord_message_id=123,
    text="Hello",
    chat_id=456,
    from_user="user",
    to_user=None,
    reply_to_message_id=None,
    reply_text=None,
    message_type="text",
)

# Adicionar mensagem (genérico)
service.add_message(
    platform="telegram",
    platform_message_id=123,
    text="Hello",
    chat_id=456,
    from_user="user",
    to_user=None,
    reply_to_message_id=None,
    reply_text=None,
    message_type="text",
    created_at=datetime.now(),
)

# Obter últimas mensagens
service.get_last_messages(
    chat_id=123,
    platform="telegram",  # ou "discord"
    limit=5,
    from_users=["user1", "user2"],
)

# Obter última mensagem por tipo
service.get_last_message_by_type(
    chat_id=123,
    message_type="text",
    platform="telegram",
)

# Atualizar texto da mensagem
service.update_message_text(
    platform_message_id=123,
    text="Updated text",
    platform="telegram",
)

# Obter mensagem por ID
service.get_message(message_id=1)
```

## API do FeatureService

```python
from domain import FeatureService

service = FeatureService()

# Adicionar feature
service.add_feature(name="my_feature", status=True)

# Remover feature
service.remove_feature(name="my_feature")

# Toggle feature
service.toggle_feature(name="my_feature")

# Obter status
service.get_feature_status(name="my_feature")

# Verificar se está habilitada
service.is_feature_enabled(name="my_feature")
```

## Benefícios

1. **Testabilidade**: Services podem ser testados isoladamente com mocks
2. **Desacoplamento**: Bots não conhecem detalhes de implementação do banco
3. **Extensibilidade**: Fácil adicionar novas funcionalidades ou trocar o ORM
4. **Domain-Driven Design**: Lógica de negócio centralizada no domínio
5. **Plataforma Agnóstica**: Mesma tabela e serviço para Telegram e Discord
6. **Injeção de Dependência**: Repositories podem ser injetados em services
7. **Separação de Responsabilidades**: Entidades, Repositories e Services separados
8. **Backward Compatibility**: Métodos antigos ainda funcionam (add_telegram_message)

## Testes

Todos os testes passaram:
- ✅ MessageService testado com Telegram e Discord
- ✅ FeatureService testado completamente
- ✅ Cross-platform messages testadas
- ✅ Todos os bots importam corretamente
- ✅ Migração de schema executada com sucesso

## Próximos Passos

A reestruturação está completa. Possíveis melhorias futuras:
- Adicionar cache nos services
- Implementar transações
- Adicionar validações nas entidades
- Criar interfaces para repositories (Protocol)
- Adicionar logs mais detalhados
- Implementar repositórios específicos por plataforma
