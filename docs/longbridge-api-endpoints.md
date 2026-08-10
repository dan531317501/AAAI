# Longbridge REST API Endpoint Index

This table lists only the documented HTTP REST endpoints implemented by
`longbridge_rest_client`. Real-time quotes, order-book depth, broker queues,
and trade ticks are delivered through the separate quote WebSocket/TCP feed.

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/watchlist/groups` | Get all watchlist groups for the current user. |
| `POST /v1/watchlist/groups` | Create a watchlist group and optionally add securities. |
| `PUT /v1/watchlist/groups` | Update a watchlist name or apply a security add/remove/replace operation. |
| `DELETE /v1/watchlist/groups` | Delete a watchlist group, optionally purging its securities first. |
| `GET /v1/quote/get_security_list` | Query tradable securities filtered by market and category. |
| `GET /v1/quote/history_market_temperature` | Get historical market temperature, valuation, and sentiment scores. |
| `GET /v1/quote/market_temperature` | Get the current market temperature snapshot. |
| `GET /v1/asset/cashflow` | Query account cash-flow history with optional filters and pagination. |
| `GET /v1/asset/account` | Query account cash, buying power, margin, and per-currency cash details. |
| `GET /v1/asset/stock` | Query stock positions grouped by sub-account channel. |
| `GET /v1/asset/fund` | Query public fund positions grouped by sub-account channel. |
| `GET /v1/statement/list` | List available daily or monthly account statements. |
| `GET /v1/statement/download` | Get a presigned URL for downloading an account statement. |
| `GET /v1/quote/filings` | Query regulatory filings for a security symbol. |
| `GET /v1/content/{symbol}/news` | Query news articles associated with a security symbol. |
| `GET /v1/content/{symbol}/topics` | List community topics associated with a security symbol. |
| `GET /v1/content/topics/mine` | List topics published by the current user. |
| `POST /v1/content/topics` | Create a community article or short post. |
| `GET /v1/content/topics/{id}` | Get the detail of a community topic. |
| `GET /v1/content/topics/{topic_id}/comments` | List comments and replies for a community topic. |
| `POST /v1/content/topics/{topic_id}/comments` | Create a top-level comment or nested reply. |
| `GET /v1/trade/execution/history` | Query historical trade executions. |
| `GET /v1/trade/order` | Get detailed information for one order. |
| `PUT /v1/trade/order` | Modify an existing order. |
| `DELETE /v1/trade/order` | Cancel an existing order. |
| `GET /v1/trade/estimate/buy_limit` | Estimate the maximum purchasable quantity for an order. |
| `GET /v1/trade/order/history` | Query historical orders with filters and pagination. |
| `GET /v1/trade/execution/today` | Query today's trade executions. |
| `GET /v1/trade/order/today` | Query today's orders with filters and pagination. |
