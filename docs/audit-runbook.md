# HAIRA — Audit Runbook

> Como usar os logs de auditoria pra responder a perguntas reais: "quem editou X?", "houve abuso?", "que conversa com a Moon foi feita ontem?".
> Cobertura instalada em 04-05 jun 2026 (commits `1927bf2`, `fa96dca`).
> Pra arquitetura geral ver [architecture.md](architecture.md).

---

## 1. O que está sendo capturado

| Tipo | Tabela | Onde dispara |
|---|---|---|
| **Auth events** | `auth_event_log` | login_ok · login_fail (×2 paths: user not found / bad password) · logout · admin_reset_ok · admin_reset_fail |
| **Admin actions** | `admin_action_log` | moon_config.update · brand.create/update/delete · kb.created/updated/deleted |
| **KB retrievals** | `kb_retrieval_log` | cada `POST /api/moon/chat` (1 entrada por turn) |
| **Histórico geral** | `revision_history` | mutações genéricas via repository (legacy + futuro) |

Todas vivem em **`haira_audit`** (logicamente — hoje fisicamente em Postgres-Core até o cutover de Audit). Append-only, retenção 1 ano.

---

## 2. Garantias do pipeline

1. **Fire-and-forget**: nenhuma falha de audit derruba a request principal. Wrapper `_safe_commit` em `src/core/audit.py` captura tudo, loga warning, segue.
2. **Privacy by design**: queries de usuário **não** ficam armazenadas cruas. Em `kb_retrieval_log.query_hash` fica só `sha256(query)`. Permite detectar recorrência de dúvida sem PII.
3. **IPs sim, mas só pra incidente**: `auth_event_log.ip_address` é capturado pra responder ataque/fraude. Não usado pra analytics.
4. **Engine resolution com fallback**: `get_audit_session()` resolve `AUDIT_DATABASE_URL → CORE_DATABASE_URL → DATABASE_URL`. Mesmo sem split 3-DB completo, audit funciona.

---

## 3. Viewer no painel

Login admin em `https://haira-app-production-deb8.up.railway.app` → `/ops/knowledge` → aba **Auditoria**.

3 sub-views:
- **Login & Auth** — eventos com badge ok/fail, email, IP, detalhe
- **Ações Admin** — quem, ação, alvo (`brand/abc`, `kb/123`, …)
- **Consultas Moon** — quando, intent, hash da pergunta, fontes usadas, chunks

3 KPI cards no topo:
- Logins (total · ok · fail · fail_rate%)
- Ações Admin (total · top action)
- Consultas Moon (total · breakdown por intent)

Filtros disponíveis nos endpoints (não exposed na UI ainda): `email`, `event_type`, `action`, `actor_email`, `target_type`, `target_id`, `intent`, `user_id`, `date_from`, `date_to`, `limit` (max 500).

---

## 4. Playbooks

### 4.1 "Houve tentativa de invasão?"

Procurar picos de `login_fail` por IP ou email.

```sql
-- via API: GET /api/admin/audit/auth-events?event_type=login_fail&limit=500
-- via SQL direto:
SELECT email, ip_address, COUNT(*) AS attempts, MIN(created_at) AS first, MAX(created_at) AS last
FROM auth_event_log
WHERE event_type IN ('login_fail', 'admin_reset_fail')
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY email, ip_address
HAVING COUNT(*) >= 5
ORDER BY attempts DESC;
```

**Threshold de ação:** ≥ 5 fails do mesmo IP em 1h, ou ≥ 3 fails diferentes contra `admin_reset_fail` em 24h.

**Resposta imediata:**
1. Bloquear IP no Railway (CloudFlare/Edge se aplicável)
2. Conferir se houve `login_ok` subsequente do mesmo IP — se sim, **rotacionar JWT_SECRET_KEY** (invalida todas sessões)
3. Rotacionar senha do user atacado se for admin
4. Comentário em HAIRA-143

### 4.2 "Quem editou a personalidade da Moon ontem?"

```sql
SELECT actor_email, action, before, after, created_at
FROM admin_action_log
WHERE action = 'moon_config.update'
  AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

`before.len` / `after.len` mostram tamanho do prompt antes/depois (não conteúdo, pra não estourar storage).

### 4.3 "A Moon recebeu pergunta sobre saúde do couro?"

```sql
SELECT created_at, intent, chunk_count, kb_sources
FROM kb_retrieval_log
WHERE intent = 'saude_couro'
  AND created_at > NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;
```

`query_hash` é só `sha256` — não dá pra reconstruir a pergunta. Mas dá pra ver **frequência** e **quais fontes** o sistema usou.

### 4.4 "Quem deletou a marca X?"

```sql
SELECT actor_email, before, created_at
FROM admin_action_log
WHERE action = 'brand.delete'
  AND target_id = 'slug-da-marca'
ORDER BY created_at DESC
LIMIT 1;
```

`before` tem snapshot completo do brand antes do delete (servido por `_serialize_brand`). Permite restaurar dados se for engano.

### 4.5 "Credencial admin vazou — quem usou ela depois?"

Se uma senha admin vazou (ex.: print compartilhado em chat):

1. **Rotacionar imediatamente** (ver §5)
2. Investigar uso entre exposição e rotação:

```sql
SELECT created_at, ip_address, user_agent, detail
FROM auth_event_log
WHERE email = 'admin@haira.com'
  AND event_type = 'login_ok'
  AND created_at BETWEEN '<exposicao>' AND '<rotacao>'
ORDER BY created_at DESC;
```

IPs desconhecidos = suspeitos. User-agent fora do padrão também.

```sql
SELECT actor_email, action, target_type, target_id, before, after, ip_address, created_at
FROM admin_action_log
WHERE created_at BETWEEN '<exposicao>' AND '<rotacao>'
ORDER BY created_at;
```

Qualquer mutação no período → revisar. Ações fora do horário típico do admin real → suspeitas.

---

## 5. Rotação de credenciais

### 5.1 Senha admin

```bash
# Gera senha forte local (não echo em chat)
NEW_PW=$(python3 -c "import secrets,string; \
  c=string.ascii_letters+string.digits+'!@#%&*-_+='; \
  print(''.join(secrets.choice(c) for _ in range(28)))")

# Pega ADMIN_RESET_KEY do Railway (dashboard ou CLI)
RESET_KEY=$(railway variables --service haira-app --json | jq -r '.ADMIN_RESET_KEY')

# Reseta
curl -X POST "https://haira-app-production-deb8.up.railway.app/api/auth/reset-admin" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"admin@haira.com\",\"new_password\":\"$NEW_PW\",\"reset_key\":\"$RESET_KEY\"}"

# Salvar em 1Password (item "HAIRA admin prod")
echo "Salva no 1Password: $NEW_PW"
unset NEW_PW RESET_KEY
```

Log esperado: `admin_reset_ok` em `auth_event_log`.

### 5.2 ADMIN_RESET_KEY

```bash
NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
railway variables --service haira-app --set "ADMIN_RESET_KEY=$NEW_KEY"
# Redeploy automático
unset NEW_KEY
```

### 5.3 JWT_SECRET_KEY (invalida todas as sessões — usar em incidente)

```bash
NEW_JWT=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
railway variables --service haira-app --set "JWT_SECRET_KEY=$NEW_JWT"
# Redeploy automático — todos os tokens emitidos antes ficam inválidos
unset NEW_JWT
```

**Avisar os reviewers** (todas tem que re-logar).

### 5.4 KB_ENCRYPTION_KEY (mais sensível — destrói KB se feito sem re-criptografia)

⚠️ **Não rotacionar sem plano.** A KB no DB foi criptografada com a chave atual. Rotacionar quebra leitura.

Processo correto:
1. `scripts/decrypt_all_kb.py` lê KB com chave antiga → memória
2. Gera nova chave
3. `scripts/encrypt_all_kb.py` re-encripta com nova chave
4. Update env var
5. Redeploy

Sem todas essas etapas, **não rotacionar**.

---

## 6. Retenção e limpeza

- Audit logs: **1 ano** (Railway daily backup com retenção 365d)
- `revision_history`: indefinida (legacy, baixo volume)
- `kb_retrieval_log`: 1 ano (query_hash + intent ocupam pouco)
- Backup mensal pode ser exportado pra S3 frio se compliance exigir > 1 ano

Job de limpeza (planejado, não implementado):
```sql
DELETE FROM auth_event_log WHERE created_at < NOW() - INTERVAL '1 year';
DELETE FROM admin_action_log WHERE created_at < NOW() - INTERVAL '1 year';
DELETE FROM kb_retrieval_log WHERE created_at < NOW() - INTERVAL '1 year';
```

---

## 7. Validação periódica

Mensal, conferir que pipeline está vivo:

```sql
-- Cada tipo recebeu eventos nos últimos 7 dias?
SELECT 'auth'  AS kind, COUNT(*) FROM auth_event_log  WHERE created_at > NOW() - INTERVAL '7 days'
UNION ALL
SELECT 'admin', COUNT(*) FROM admin_action_log WHERE created_at > NOW() - INTERVAL '7 days'
UNION ALL
SELECT 'kb',    COUNT(*) FROM kb_retrieval_log WHERE created_at > NOW() - INTERVAL '7 days';
```

Esperado: cada count > 0. Se algum vier zerado e o sistema teve uso, investigar `src/core/audit.py` (logs no nível WARNING).

---

## 8. Endpoints úteis

| Endpoint | Filtros | Default limit |
|---|---|---|
| `GET /api/admin/audit/auth-events` | `email`, `event_type`, `date_from`, `date_to` | 100 (max 500) |
| `GET /api/admin/audit/admin-actions` | `action`, `actor_email`, `target_type`, `target_id`, `date_from`, `date_to` | 100 |
| `GET /api/admin/audit/kb-retrievals` | `intent`, `user_id`, `date_from`, `date_to` | 100 |
| `GET /api/admin/audit/summary` | (none) | n/a (KPIs all-time) |

Todos exigem `Authorization: Bearer <admin_token>`. Reviewer recebe 403.

---

## 9. Onde isso falha

- **Audit DB offline:** request principal segue, audit não loga. Warning em stdout. Monitorar via Railway logs.
- **JWT_SECRET_KEY trocada sem aviso:** todos os tokens viram inválidos. Reviewers re-logam, log fica com burst de `login_fail` (esperado).
- **Database migration falha:** novos eventos não persistem até schema alinhar. Detectar no startup do app (logger.error).

> Última revisão: 06 jun 2026
