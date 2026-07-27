import { useEffect, useState } from "react";
import { Button, Card, Text } from "@fluentui/react-components";

import { DashboardRequestError, getJson, postJson } from "../../api/client";

type Platform = {
  name: string;
  item_types: string[];
  requires_browser: boolean;
  requires_auth: boolean;
  auth_status: string;
  auth_message: string;
};

function isPlatform(value: unknown): value is Platform {
  return typeof value === "object" && value !== null
    && "name" in value && typeof value.name === "string"
    && "item_types" in value && Array.isArray(value.item_types)
    && "requires_browser" in value && typeof value.requires_browser === "boolean"
    && "requires_auth" in value && typeof value.requires_auth === "boolean"
    && "auth_status" in value && typeof value.auth_status === "string"
    && "auth_message" in value && typeof value.auth_message === "string";
}

function labelFor(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1);
}

export function PlatformsPage() {
  const [platforms, setPlatforms] = useState<Platform[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [loginPending, setLoginPending] = useState<string | null>(null);
  const [openingPlatform, setOpeningPlatform] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const result = await getJson<unknown>("/api/v1/platforms");
      if (!Array.isArray(result) || !result.every(isPlatform)) throw new Error("invalid platforms response");
      setPlatforms(result);
    } catch {
      setPlatforms(null);
      setError("Platform status is unavailable. Refresh to retry the local engine request.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function openLogin(platform: Platform) {
    setLoginPending(platform.name);
    setOpeningPlatform(null);
    setError(null);
    try {
      const response = await postJson<unknown>(`/api/v1/platforms/${encodeURIComponent(platform.name)}/login`, {});
      if (typeof response !== "object" || response === null || !("status" in response) || response.status !== "opening_browser") {
        throw new Error("invalid login response");
      }
      setOpeningPlatform(platform.name);
    } catch (reason) {
      setError(reason instanceof DashboardRequestError && reason.code === "offline"
        ? "Local engine is offline. External login was not started."
        : "External login was not confirmed by the local engine.");
    } finally {
      setLoginPending(null);
    }
  }

  return (
    <section id="platforms" aria-label="Platforms and login">
      <Card>
        <Text as="h2" size={600}>Platforms and login</Text>
        <Text>Scan the QR code in external Chromium. This dashboard never shows or stores QR or cookie data.</Text>
        <Button appearance="secondary" onClick={refresh} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh status"}
        </Button>
        {error && <Text role="alert">{error}</Text>}
        {platforms?.length === 0 && <Text role="status">No platform adapters are configured.</Text>}
        {platforms?.map((platform) => (
          <Card key={platform.name}>
            <Text as="h3" size={500}>{labelFor(platform.name)}</Text>
            <Text className="metric">{platform.auth_status} · {platform.item_types.join(", ") || "no item types"}</Text>
            <Text>{platform.auth_message}</Text>
            {platform.requires_auth && platform.requires_browser && <Button
              appearance="primary"
              onClick={() => void openLogin(platform)}
              disabled={loginPending !== null}
            >
              {loginPending === platform.name ? "Opening external login..." : `Open ${labelFor(platform.name)} login`}
            </Button>}
            {openingPlatform === platform.name && <Text role="status">External Chromium is opening. Complete the scan there, then refresh platform status.</Text>}
          </Card>
        ))}
      </Card>
    </section>
  );
}
