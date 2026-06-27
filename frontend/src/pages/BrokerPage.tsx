import { useEffect, useState } from "react";
import { API_BASE_URL, api, BrokerAccount, BrokerPosition, BrokerStatus } from "../api/client";
import { StatCard } from "../components/StatCard";

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function booleanStatus(value: boolean | undefined, trueLabel: string, falseLabel: string) {
  if (value === undefined) return "Unknown";
  return value ? trueLabel : falseLabel;
}

export function BrokerPage() {
  const [status, setStatus] = useState<BrokerStatus | null>(null);
  const [accounts, setAccounts] = useState<BrokerAccount[]>([]);
  const [positions, setPositions] = useState<BrokerPosition[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = () => {
    Promise.allSettled([api.getBrokerStatus(), api.getBrokerAccounts(), api.getBrokerPositions()])
      .then(([statusResult, accountResult, positionResult]) => {
        const messages: string[] = [];

        if (statusResult.status === "fulfilled") {
          setStatus(statusResult.value);
        } else {
          setStatus(null);
          messages.push(`Broker status is not available: ${errorMessage(statusResult.reason, "Request failed")}`);
        }

        if (accountResult.status === "fulfilled") {
          const accountResponse = accountResult.value;
          setAccounts(accountResponse.accounts ?? []);
          if (!accountResponse.success) {
            messages.push(accountResponse.message ?? accountResponse.status ?? "Broker accounts are not available.");
          }
        } else {
          setAccounts([]);
          messages.push(`Broker accounts are not available: ${errorMessage(accountResult.reason, "Request failed")}`);
        }

        if (positionResult.status === "fulfilled") {
          const positionResponse = positionResult.value;
          setPositions(positionResponse.positions ?? []);
          if (!positionResponse.success) {
            messages.push(positionResponse.message ?? positionResponse.status ?? "Broker holdings are not available.");
          }
        } else {
          setPositions([]);
          messages.push(`Broker holdings are not available: ${errorMessage(positionResult.reason, "Request failed")}`);
        }

        setMessage(messages.length ? messages.join(" ") : null);
      });
  };

  useEffect(() => {
    refresh();
  }, []);

  const syncLegacy = () => {
    api.syncLegacyFromBroker()
      .then((result) => setMessage(result.message ?? `${result.imported_count} imported, ${result.skipped_count} skipped.`))
      .catch(() => setMessage("Broker legacy sync failed."));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">Toss Securities</p>
          <h2>Broker Account</h2>
          <p className="helper-text">API base: {API_BASE_URL}</p>
        </div>
        <button className="secondary-button" onClick={refresh} type="button">Refresh</button>
        <button className="primary-button" onClick={syncLegacy} type="button">Sync Legacy</button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="API Credentials" value={booleanStatus(status?.api_credentials_ready, "Ready", "Incomplete")} />
        <StatCard label="Account Lookup" value={booleanStatus(status?.account_lookup_ready, "Ready", "Not Ready")} />
        <StatCard label="Account ID" value={booleanStatus(status?.has_account_id, "Set", "Missing")} />
        <StatCard label="Holdings Lookup" value={booleanStatus(status?.read_only_ready, "Ready", "Not Ready")} />
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
                  <td colSpan={3}>No broker accounts loaded.</td>
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
                  <td>{position.quantity.toLocaleString()}</td>
                  <td>{position.avg_price.toLocaleString()}</td>
                  <td>{position.current_price.toLocaleString()}</td>
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
