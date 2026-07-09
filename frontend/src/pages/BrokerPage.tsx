import { useEffect, useRef, useState } from "react";
import { API_BASE_URL, api, BrokerAccount, BrokerPosition, BrokerStatus, HealthResponse } from "../api/client";
import { StatCard } from "../components/StatCard";

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function booleanStatus(value: boolean | undefined, trueLabel: string, falseLabel: string) {
  if (value === undefined) return "알 수 없음";
  return value ? trueLabel : falseLabel;
}

function formatOptionalNumber(value: number) {
  return value > 0 ? value.toLocaleString() : "-";
}

function brokerResponseMessage(label: string, response: { status: string; http_status_code?: number | null; message?: string }) {
  const statusCode = response.http_status_code ? `HTTP ${response.http_status_code}` : response.status;
  if (response.http_status_code === 401) {
    return `${label} 실패: ${statusCode} - 토스 인증 정보와 조회 권한을 확인하세요.`;
  }
  if (response.http_status_code === 429) {
    return `${label} 실패: ${statusCode} - 토스 호출 한도에 도달했습니다. 잠시 후 다시 시도하세요.`;
  }
  return `${label} 실패: ${statusCode}${response.message ? ` - ${response.message}` : ""}`;
}

export function BrokerPage() {
  const didInitialLoad = useRef(false);
  const cooldownTimers = useRef<number[]>([]);
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

  const startCooldown = (setCooldown: (value: boolean) => void) => {
    setCooldown(true);
    const timerId = window.setTimeout(() => setCooldown(false), 15000);
    cooldownTimers.current.push(timerId);
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
          appendMessage(brokerResponseMessage("계좌 조회", accountResponse));
          if (accountResponse.http_status_code === 429) {
            startCooldown(setIsAccountCooldown);
          }
        }
      })
      .catch((error) => {
        setAccounts([]);
        setAccountsCacheHit(null);
        appendMessage(`브로커 계좌를 불러올 수 없습니다: ${errorMessage(error, "요청 실패")}`);
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
          appendMessage(`백엔드 상태를 확인할 수 없습니다: ${errorMessage(error, "요청 실패")}`);
        }),
      api.getBrokerStatus()
        .then((brokerStatus) => setStatus(brokerStatus))
        .catch((error) => {
          setStatus(null);
          appendMessage(`브로커 상태를 확인할 수 없습니다: ${errorMessage(error, "요청 실패")}`);
        }),
      api.getBrokerPositions()
        .then((positionResponse) => {
          setPositions(positionResponse.positions ?? []);
          setPositionsCacheHit(positionResponse.cache_hit);
          if (!positionResponse.success) {
            appendMessage(brokerResponseMessage("잔고 조회", positionResponse));
            if (positionResponse.http_status_code === 429) {
              startCooldown(setIsRefreshCooldown);
            }
          }
        })
        .catch((error) => {
          setPositions([]);
          setPositionsCacheHit(null);
          appendMessage(`브로커 잔고를 불러올 수 없습니다: ${errorMessage(error, "요청 실패")}`);
        }),
    ]).finally(() => setIsRefreshing(false));
  };

  useEffect(() => {
    if (didInitialLoad.current) return;
    didInitialLoad.current = true;
    refresh();
    return () => {
      cooldownTimers.current.forEach((timerId) => window.clearTimeout(timerId));
      cooldownTimers.current = [];
    };
  }, []);

  const syncLegacy = () => {
    if (isSyncingLegacy) return;
    setIsSyncingLegacy(true);
    setMessage(null);
    api.syncLegacyFromBroker()
      .then((result) => setMessage(result.message ?? `${result.imported_count}개 가져옴, ${result.skipped_count}개 건너뜀.`))
      .catch(() => setMessage("브로커 기존 보유분 동기화에 실패했습니다."))
      .finally(() => setIsSyncingLegacy(false));
  };

  return (
    <section className="page-stack">
      <header className="page-header">
        <div>
          <p className="eyebrow">토스증권</p>
          <h2>브로커 계좌</h2>
          <p className="helper-text">API 기준 주소: {API_BASE_URL}</p>
        </div>
        <button className="secondary-button" disabled={isRefreshing || isRefreshCooldown} onClick={refresh} type="button">
          {isRefreshing ? "새로고침 중..." : isRefreshCooldown ? "대기..." : "새로고침"}
        </button>
        <button className="secondary-button" disabled={isLoadingAccounts || isAccountCooldown} onClick={refreshAccounts} type="button">
          {isLoadingAccounts ? "불러오는 중..." : isAccountCooldown ? "대기..." : "계좌 불러오기"}
        </button>
        <button className="primary-button" disabled={isSyncingLegacy} onClick={syncLegacy} type="button">
          {isSyncingLegacy ? "동기화 중..." : "기존 보유분 동기화"}
        </button>
      </header>
      {message ? <div className="notice">{message}</div> : null}
      <div className="stat-grid">
        <StatCard label="백엔드 API" value={backendHealth?.status === "ok" ? "온라인" : "알 수 없음"} detail={backendHealth?.dry_run ? "모의 실행 백엔드" : undefined} />
        <StatCard label="API 인증 정보" value={booleanStatus(status?.api_credentials_ready, "준비됨", "미완료")} />
        <StatCard
          label="계좌 조회"
          value={booleanStatus(status?.account_lookup_ready, "준비됨", "미준비")}
          detail={accountsCacheHit === null ? undefined : accountsCacheHit ? "캐시 응답" : "최신 응답"}
        />
        <StatCard label="계좌 ID" value={booleanStatus(status?.has_account_id, "설정됨", "누락")} />
        <StatCard
          label="잔고 조회"
          value={booleanStatus(status?.read_only_ready, "준비됨", "미준비")}
          detail={positionsCacheHit === null ? undefined : positionsCacheHit ? "캐시 응답" : "최신 응답"}
        />
        <StatCard label="모의 데이터" value={booleanStatus(status?.use_mock_data, "켜짐", "꺼짐")} />
        <StatCard label="모의 실행" value={booleanStatus(status?.dry_run, "켜짐", "꺼짐")} />
      </div>
      <section>
        <h3>계좌</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>계좌</th>
                <th>계좌 순번</th>
                <th>유형</th>
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
                  <td colSpan={3}>토스 호출 한도를 피하기 위해 계좌는 필요할 때만 불러옵니다.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
      <section>
        <h3>잔고</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>종목</th>
                <th>이름</th>
                <th>수량</th>
                <th>평균가</th>
                <th>현재가</th>
                <th>소스</th>
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
                  <td colSpan={6}>불러온 잔고가 없습니다.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
