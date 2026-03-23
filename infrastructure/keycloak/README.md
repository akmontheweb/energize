# Keycloak Realm Setup

## Automatic Import (Docker Compose)

The realm is automatically imported when starting via Docker Compose:

```bash
docker compose up keycloak
```

The `realm-export.json` is mounted to `/opt/keycloak/data/import/` and Keycloak
starts with `--import-realm`, so the **energize** realm is created on first boot.

## Manual Import (Keycloak Admin UI)

1. Start Keycloak and browse to <http://localhost:8080>
2. Log in with `admin / admin`
3. Hover over the realm dropdown (top-left) → **Create Realm**
4. Click **Browse** and select `keycloak/realm-export.json`
5. Click **Create**

## Manual Import (CLI)

```bash
docker exec -it energize-keycloak \
  /opt/keycloak/bin/kc.sh import \
  --file /opt/keycloak/data/import/realm-export.json
```

## Realm Details

| Setting | Value |
|---|---|
| Realm name | `energize` |
| Admin console | <http://localhost:8080/admin/master/console/> |
| OIDC discovery | <http://localhost:8080/realms/energize/.well-known/openid-configuration> |

## Roles

| Role | Description |
|---|---|
| `client` | Regular coaching client (default role for new registrations) |
| `coach` | Certified coach who runs sessions |
| `admin` | Platform administrator |

## Clients

| Client ID | Type | Purpose |
|---|---|---|
| `energize-frontend` | Public (PKCE) | Next.js SPA |
| `energize-backend` | Confidential (bearer-only) | FastAPI backend |

## Security Settings

- **Password policy**: minimum 12 characters, 1 uppercase, 1 digit, 1 special character
- **Access token lifespan**: 15 minutes (900 s)
- **Refresh / SSO session**: 8 hours (28 800 s)
- **PKCE**: required for the frontend client (`S256`)
- **Email verification**: disabled for development

## Assigning Roles to Users

1. Open Admin UI → **energize** realm → **Users**
2. Select the user → **Role Mapping** tab
3. Assign `coach` or `admin` as needed (`client` is assigned by default)
