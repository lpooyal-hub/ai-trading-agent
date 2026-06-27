from typing import Any


class BrokerAccountNormalizer:
    account_no_keys = (
        "accountNo",
        "account_no",
        "accountNumber",
        "account_number",
        "accountId",
        "account_id",
        "account",
    )
    account_seq_keys = ("accountSeq", "account_seq", "sequence", "seq")
    account_type_keys = ("accountType", "account_type", "productType", "product_type", "type")

    def normalize_accounts(self, payload: Any) -> list[dict]:
        rows = self._find_account_rows(payload)
        accounts: list[dict] = []
        for row in rows:
            account = self._normalize_row(row)
            if account:
                accounts.append(account)
        return accounts

    def _find_account_rows(self, payload: Any) -> list[dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []

        candidate_keys = (
            "result",
            "accounts",
            "accountList",
            "account_list",
            "items",
            "data",
            "body",
            "content",
            "output",
        )
        for key in candidate_keys:
            value = payload.get(key)
            rows = self._find_account_rows(value)
            if rows:
                return rows
        return []

    def _normalize_row(self, row: dict) -> dict | None:
        account_no = self._first_text(row, self.account_no_keys)
        if not account_no:
            return None

        return {
            "masked_account_no": self._mask_account_no(account_no),
            "account_seq": self._first_int(row, self.account_seq_keys),
            "account_type": self._first_text(row, self.account_type_keys),
            "source": "toss_read_only",
        }

    @staticmethod
    def _first_text(row: dict, keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _first_int(row: dict, keys: tuple[str, ...]) -> int | None:
        for key in keys:
            value = row.get(key)
            if value is None or value == "":
                continue
            try:
                return int(str(value).replace(",", ""))
            except ValueError:
                continue
        return None

    @staticmethod
    def _mask_account_no(account_no: str) -> str:
        normalized = account_no.strip()
        if len(normalized) <= 4:
            return "****"
        return f"{normalized[:3]}****{normalized[-4:]}"
