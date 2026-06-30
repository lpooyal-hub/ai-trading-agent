# Frontend Dashboard

React + TypeScript + Vite 기반의 관리자 대시보드입니다.

현재 화면은 DRY_RUN / mock data 중심의 연구용 UI입니다.
Dashboard의 `Seed Demo Data` 버튼은 backend `/demo/seed`를 호출해 fictional sample data를 생성합니다.
이 버튼은 demo mode가 활성화된 경우에만 사용할 수 있습니다.

## 주요 화면

- Dashboard
- Decisions
- Decision Detail
- Orders
- Broker
- Portfolio
- Evaluations
- LLM Usage
- Settings

## 실행 명령어

아래 명령은 사용자가 직접 실행합니다.

```bash
cd /home/ubuntu/ai-trading-agent/frontend
npm install
npm run dev
```

Docker Compose를 사용할 경우 프로젝트 루트에서 실행합니다.

```bash
cd /home/ubuntu/ai-trading-agent
docker compose up --build
```

Docker Compose 기본 frontend 주소는 `http://localhost:3000`입니다. 운영 도메인을 붙일 때도 대시보드는 기본적으로 `/api` proxy를 통해 backend container로 요청을 전달합니다.

Frontend API 주소는 `VITE_API_BASE_URL`이 있으면 그 값을 우선 사용합니다. 값이 없으면 기본값 `/api`를 사용합니다.

- `http://localhost:5173`에서 열면 local backend `http://localhost:8000`
- Docker Compose에서 `http://localhost:3000` 또는 운영 도메인으로 열면 `/api` proxy를 통해 backend container `http://backend:8000`

Backend 주소를 직접 고정해야 할 때만 `.env` 또는 실행 환경에 아래 값을 설정합니다.

```bash
VITE_API_BASE_URL=http://localhost:81
```

운영 도메인에서는 `VITE_API_BASE_URL`을 비워두고 Nginx의 `/api` reverse proxy를 사용하는 것을 권장합니다. 외부 서버에서 backend 주소를 직접 고정해야 할 때만 `localhost` 대신 서버 IP 또는 별도 backend 도메인을 사용합니다.

```bash
VITE_API_BASE_URL=http://<SERVER_IP>:81
```

운영 도메인 뒤에서 Vite dev server를 그대로 노출하는 경우에는 host allowlist도 실제 서버 환경에 설정합니다.

```bash
VITE_ALLOWED_HOSTS=your-trading-domain.example
```
