import { useEffect, useRef, useState } from "react";
import { API_BASE_URL, api, BrokerAccount, BrokerPosition, BrokerStatus, HealthResponse } from "../api/client";
import { StatCard } from "../components/StatCard";

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function booleanStatus(value: boolean | undefined, trueLabel: string, falseLabel: string) {
  if (value === undefined) return "Unknown";
  return value ? trueLabel : falseLabel;
}

function formatOptionalNumber(value: number) {
  return value > 0 ? value.toLocaleString() : "-";
}

function brokerResponseMessage(label: string, response: { status: string; http_status_code?: number | null; message?: string }) {
  const statusCode = response.http_status_code ? `HTTP ${response.http_status_code}` : response.status;
  if (response.http_status_code === 401) {
    return `${label} failed: ${statusCode} - Check Toss credentials and read-only account permissions.`;
  }
  if (response.http_status_code === 429) {
    return `${label} failed: ${statusCode} - Toss rate limit reached. Wait briefly before retrying.`;
  }
  return `${label} failed: ${statusCode}${response.message ? ` - ${response.message}` : ""}`;
}

export function BrokerPage() {
  const didInitialLoad = useRef(false);
  const [backendHealth, setBackendHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<BrokerStatus | null>(null);
  const [accounts, setAccounts] = useState<BrokerAccount[]>([]);
  const [positions, setPositions] = useState<BrokerPosition[]>([]);
  const [accountsCacheHit, setAccountsCacheHit] = useState<boolean | null>(null);
  const [positionsCacheHit, setPositionsCacheHit] = useState<boolean | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isRefreshCooldown, setIsRefreshCooldown] = useState(false);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(false);
  const [isAccountCooldown, setIsAccountCooldown] = useState(false);
  const [isSyncingLegacy, setIsSyncingLegacy] = useState(false);

  const appendMessage = (nextMessage: string) => {
    setMessage((current) => {
      if (!current) return nextMessage;
      return current.includes(nextMessage) ? current : `${current} ${nextMessage}`;
    });
  };

  const refreshAccounts = () => {
    if (isLoadingAccounts || isAccountCooldown) return;
    setIsLoadingAccounts(true);
    setMessage(null);
    api.getBrokerAccounts()
      .then((accountResponse) => {
        setAccounts(accountResponse.accounts ?? []);
        setAccountsCacheHit(accountResponse.cache_hit);
        if (!accountResponse.success) {
          appendMessage(brokerResponseMessage("Accounts lookup", accountResponse));
          if (accountResponse.http_status_code === 429) {
            setIsAccountCooldown(true);
            window.setTimeout(() => setIsAccountCooldown(false), 15000);
          }
        }
      })
      .catch((error) => {
        setAccounts([]);
        setAccountsCacheHit(null);
        appendMessage(`Broker accounts are not available: ${errorMessage(error, "Request failed")}`);
      })
      .finally(() => setIsLoadingAccounts(false));
  };

  const refresh = () => {
    if (isRefreshing || isRefreshCooldown) return;
    setIsRefreshing(true);
    setMessage(null);

    Promise.allSettled([
      api.getHealth()
        .then((health) => setBackendHealth(health))
        .catch((error) => {
          setBackendHealth(null);
          appendMessage(`Backend health is not available: ${errorMessage(error, "Request failed")}`);
        }),
      api.getBrokerStatus()
        .then((brokerStatus) => setStatus(brokerStatus))
        .catch((error) => {
          setStatus(null);
          appendMessage(`Broker status is not available: ${errorMessage(error, "Request failed")}`);
        }),
      api.getBrokerPositions()
        .then((positionResponse) => {
          setPositions(positionResponse.positions ?? []);
          setPositionsCacheHit(positionResponse.cache_hit);
          if (!positionResponse.success) {
            appendMessage(brokerResponseMessage("Holdings lookup", positionResponse));
            if (positionResponse.http_status_code === 429) {
              setIsRefreshCooldown(true);
              window.setTimeout(() => setIsRefreshCooldown(false), 15000);
            }
          }
        })
        .catch((error) => {
          setPositions([]);
          setPositionsCacheHit(null);
          appendMessage(`Broker holdings are not available: ${errorMessage(error, "Request failed")}`);
        }),
    ]).finally(() => setIsRefreshing(false));
  };

  useEffect(() => {
    if (didInitialLoad.current) return;
    didInitialLoad.current = true;
    refresh();
  }, []);

  const syncLegacy = () => {
    if (isSyncingLegacy) return;
    setIsSyncingLegacy(true);
    setMessage(null);
    api.syncLegacyFromBroker()
      .then((result) => setMessage(result.message ?? `${result.imported_count} imported, ${result.skipped_count} skipped.`))
      .catch(() => setMessage("Broker legacy sync failed."))
      .finally(() => setIsSyncingLegacy(false));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Toss Securities</p>
          <h2>Broker Account</h2>
          <p className="helper-text">API base: {API_BASE_URL}</p>
        </div>
        <button className="secondary-button" disabled={isRefreshing || isRefreshCooldown} onClick={refresh} type="button">
          {isRefreshing ? "Refreshing..." : isRefreshCooldown ? "Wait..." : "Refresh"}
        </button>
        <button className="secondary-button" disabled={isLoadingAccounts || isAccountCooldown} onClick={refreshAccounts} type="button">
          {isLoadingAccounts ? "Loading..." : isAccountCooldown ? "Wait..." : "Load Accounts"}
        </button>
        <button className="primary-button" disabled={isSyncingLegacy} onClick={syncLegacy} type="button">
          {isSyncingLegacy ? "Syncing..." : "Sync Legacy"}
        </button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="Backend API" value={backendHealth?.status === "ok" ? "Online" : "Unknown"} detail={backendHealth?.dry_run ? "DRY_RUN backend" : undefined} />
        <StatCard label="API Credentials" value={booleanStatus(status?.api_credentials_ready, "Ready", "Incomplete")} />
        <StatCard
          label="Account Lookup"
          value={booleanStatus(status?.account_lookup_ready, "Ready", "Not Ready")}
          detail={accountsCacheHit === null ? undefined : accountsCacheHit ? "cached response" : "fresh response"}
        />
        <StatCard label="Account ID" value={booleanStatus(status?.has_account_id, "Set", "Missing")} />
        <StatCard
          label="Holdings Lookup"
          value={booleanStatus(status?.read_only_ready, "Ready", "Not Ready")}
          detail={positionsCacheHit === null ? undefined : positionsCacheHit ? "cached response" : "fresh response"}
        />
        <StatCard label="Mock Data" value={booleanStatus(status?.use_mock_data, "On", "Off")} />
        <StatCard label="DRY_RUN" value={booleanStatus(status?.dry_run, "On", "Off")} />
      </div>
      <section>
        <h3>Accounts</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Account</th>
                <th>Account Seq</th>
                <th>Type</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={`${account.account_seq}-${account.masked_account_no}`}>
                  <td>{account.masked_account_no}</td>
                  <td>{account.account_seq ?? "-"}</td>
                  <td>{account.account_type ?? "-"}</td>
                </tr>
              ))}
              {!accounts.length ? (
                <tr>
                  <td colSpan={3}>Accounts are loaded on demand to avoid Toss rate limits.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      <section>
        <h3>Holdings</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Name</th>
                <th>Quantity</th>
                <th>Avg Price</th>
                <th>Current Price</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((position) => (
                <tr key={position.symbol}>
                  <td>{position.symbol}</td>
                  <td>{position.name}</td>
                  <td>{formatOptionalNumber(position.quantity)}</td>
                  <td>{formatOptionalNumber(position.avg_price)}</td>
                  <td>{formatOptionalNumber(position.current_price)}</td>
                  <td>{position.source}</td>
                </tr>
              ))}
              {!positions.length ? (
                <tr>
                  <td colSpan={6}>No holdings loaded.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
