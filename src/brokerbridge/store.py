import hashlib
import secrets
import sqlite3
import time
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from brokerbridge.models import Order, OrderRequest, Policy, currency_for


class Store:
    """Local durable state. SQLite serializes policy checks and order insertion together."""

    def __init__(self, directory: Path):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = directory / "brokerbridge.sqlite3"
        self.path.touch(mode=0o600, exist_ok=True)
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS proposals (
                    token_hash TEXT PRIMARY KEY, request TEXT NOT NULL, expires REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orders (
                    key TEXT PRIMARY KEY, request TEXT NOT NULL, result TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY, at REAL NOT NULL, action TEXT NOT NULL,
                    outcome TEXT NOT NULL
                );
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def audit(self, action: str, outcome: str) -> None:
        # Record metadata only: never log keys, tokens, request args or account data.
        with self.db() as db:
            db.execute(
                "INSERT INTO audit(at,action,outcome) VALUES (?,?,?)",
                (time.time(), action, outcome),
            )

    @staticmethod
    def check(db, request: OrderRequest, policy: Policy):
        if policy.read_only or db.execute("SELECT 1 FROM state WHERE key='halted'").fetchone():
            raise ValueError("Paper orders are disabled by policy or kill switch")
        if request.symbol not in policy.allowed_symbols:
            raise ValueError("Symbol is not allowed by paper policy")
        currency = currency_for(request.symbol)
        value = request.limit_price * request.quantity
        if value > policy.max_order_value[currency]:
            raise ValueError("Order exceeds paper notional limit")
        open_value = Decimal(0)
        for (raw,) in db.execute("SELECT result FROM orders"):
            order = Order.model_validate_json(raw)
            if order.status == "open" and currency_for(order.symbol) == currency:
                open_value += order.quantity * order.limit_price
        if open_value + value > policy.max_open_value[currency]:
            raise ValueError("Open paper orders would exceed aggregate currency limit")

    def propose(self, request: OrderRequest, policy: Policy) -> dict:
        with self.db() as db:
            existing = db.execute(
                "SELECT request FROM orders WHERE key=?", (request.idempotency_key,)
            ).fetchone()
            if existing:
                raise ValueError("Idempotency key already executed; query orders instead")
            self.check(db, request, policy)
            token = secrets.token_urlsafe(32)
            expires = time.time() + policy.proposal_ttl_seconds
            db.execute("DELETE FROM proposals WHERE expires<?", (time.time(),))
            db.execute(
                "INSERT INTO proposals VALUES (?,?,?)",
                (hashlib.sha256(token.encode()).hexdigest(), request.model_dump_json(), expires),
            )
        return {
            "request": request.model_dump(mode="json"),
            "confirmation_token": token,
            "expires_at_unix": expires,
            "environment": "synthetic",
            "warning": "Local sandbox only. Open orders never fill or reach a broker.",
        }

    def confirm(self, token: str, policy: Policy) -> Order:
        with self.db() as db:
            row = db.execute(
                "SELECT request,expires FROM proposals WHERE token_hash=?",
                (hashlib.sha256(token.encode()).hexdigest(),),
            ).fetchone()
            if not row or row[1] <= time.time():
                raise ValueError("Unknown or expired proposal; propose again")
            request = OrderRequest.model_validate_json(row[0])
            previous = db.execute(
                "SELECT request,result FROM orders WHERE key=?", (request.idempotency_key,)
            ).fetchone()
            if previous:
                if previous[0] != request.model_dump_json():
                    raise ValueError("Idempotency key conflicts with a different order")
                return Order.model_validate_json(previous[1])
            self.check(db, request, policy)
            order = Order(
                broker_id="paper",
                order_id=secrets.token_hex(16),
                symbol=request.symbol,
                side=request.side,
                quantity=request.quantity,
                limit_price=request.limit_price,
                status="open",
                environment="synthetic",
            )
            db.execute(
                "INSERT INTO orders VALUES (?,?,?)",
                (request.idempotency_key, request.model_dump_json(), order.model_dump_json()),
            )
            db.execute(
                "INSERT INTO audit(at,action,outcome) VALUES (?,?,?)",
                (time.time(), "paper_order_created", order.order_id),
            )
            return order

    def orders(self) -> list[Order]:
        with self.db() as db:
            return [
                Order.model_validate_json(r[0]) for r in db.execute("SELECT result FROM orders")
            ]

    def cancel(self, order_id: str) -> Order:
        with self.db() as db:
            for key, raw in db.execute("SELECT key,result FROM orders"):
                order = Order.model_validate_json(raw)
                if order.order_id == order_id:
                    order = order.model_copy(update={"status": "cancelled"})
                    db.execute(
                        "UPDATE orders SET result=? WHERE key=?", (order.model_dump_json(), key)
                    )
                    db.execute(
                        "INSERT INTO audit(at,action,outcome) VALUES (?,?,?)",
                        (time.time(), "paper_order_cancelled", order_id),
                    )
                    return order
            raise ValueError("Unknown local paper order")

    def halt(self) -> dict:
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO state VALUES ('halted','true')")
            db.execute(
                "INSERT INTO audit(at,action,outcome) VALUES (?,?,?)",
                (time.time(), "kill_switch", "halted"),
            )
        return {
            "halted": True,
            "scope": "new local paper orders; existing orders are not cancelled",
        }

    def resume(self) -> None:
        with self.db() as db:
            db.execute("DELETE FROM state WHERE key='halted'")
            db.execute(
                "INSERT INTO audit(at,action,outcome) VALUES (?,?,?)",
                (time.time(), "human_cli_resume", "resumed"),
            )

    def halted(self) -> bool:
        with self.db() as db:
            return db.execute("SELECT 1 FROM state WHERE key='halted'").fetchone() is not None
