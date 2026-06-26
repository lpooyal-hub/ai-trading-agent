# Frontend Dashboard

React + TypeScript + Vite 기반의 관리자 대시보드입니다.

현재 화면은 DRY_RUN / mock data 중심의 연구용 UI입니다.

## 주요 화면

- Dashboard
- Decisions
- Decision Detail
- Orders
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

Backend 주소를 바꾸려면 `.env` 또는 실행 환경에 아래 값을 설정합니다.

```bash
VITE_API_BASE_URL=http://localhost:8000
```
