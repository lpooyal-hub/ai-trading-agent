import { useEffect, useState } from "react";
import { api, BrokerAccount, BrokerPosition, BrokerStatus } from "../api/client";
import { StatCard } from "../components/StatCard";

function maskAccountNo(accountNo?: string) {
  if (!accountNo) return "-";
  if (accountNo.length <= 4) return "****";
  return `${accountNo.slice(0, 3)}****${accountNo.slice(-4)}`;
}

export function BrokerPage() {
  const [status, setStatus] = useState<BrokerStatus | null>(null);
  const [accounts, setAccounts] = useState<BrokerAccount[]>([]);
  const [positions, setPositions] = useState<BrokerPosition[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = () => {
    Promise.all([api.getBrokerStatus(), api.getBrokerAccounts(), api.getBrokerPositions()])
      .then(([brokerStatus, accountResponse, positionResponse]) => {
        setStatus(brokerStatus);
        setAccounts(accountResponse.data?.result ?? []);
        setPositions(positionResponse.positions ?? []);
        setMessage(positionResponse.success ? null : positionResponse.message ?? positionResponse.status);
      })
      .catch(() => setMessage("Broker data is not available."));
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
        </div>
        <button className="secondary-button" onClick={refresh} type="button">Refresh</button>
        <button className="primary-button" onClick={syncLegacy} type="button">Sync Legacy</button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="Credentials" value={status?.credentials_ready ? "Ready" : "Incomplete"} />
        <StatCard label="Read Only" value={status?.read_only_ready ? "Ready" : "Not Ready"} />
        <StatCard label="Mock Data" value={status?.use_mock_data ? "On" : "Off"} />
        <StatCard label="DRY_RUN" value={status?.dry_run ? "On" : "Off"} />
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
                <tr key={`${account.accountSeq}-${account.accountNo}`}>
                  <td>{maskAccountNo(account.accountNo)}</td>
                  <td>{account.accountSeq ?? "-"}</td>
                  <td>{account.accountType ?? "-"}</td>
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
