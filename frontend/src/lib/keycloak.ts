import Keycloak from 'keycloak-js';

let keycloak: Keycloak | null = null;

export function getKeycloak(): Keycloak {
  if (!keycloak) {
    const keycloakUrl = process.env.NEXT_PUBLIC_KEYCLOAK_URL || 'http://localhost:8080';
    const keycloakRealm = process.env.NEXT_PUBLIC_KEYCLOAK_REALM || 'energize';
    const keycloakClientId = process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID || 'energize-frontend';

    keycloak = new Keycloak({
      url: keycloakUrl,
      realm: keycloakRealm,
      clientId: keycloakClientId,
    });
  }
  return keycloak;
}

export default getKeycloak;
