"use client";

/**
 * Коннекторы: откуда бот берёт то, чего нет в материалах.
 *
 * Материалы отвечают на «сколько стоит» и «как долго везёте». На «где моя
 * тридцать вторая заявка» отвечает чужая система, и коннектор — дорога к ней.
 *
 * Экран рассчитан не на программиста, но и не притворяется, что настройка
 * тривиальна: адрес, заголовок, ключ, потом инструменты с описанием и
 * параметрами. Поэтому здесь же стоит проба — единственный способ увидеть,
 * что ответит чужая система и что из этого разберёт бот, не дожидаясь
 * посетителя.
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { engineApi, reportEngineError } from "@/lib/engine-client";

interface Connector {
  id: string;
  name: string;
  base_url: string;
  headers_template: Record<string, string>;
  has_secret: boolean;
}

interface Tool {
  id: string;
  connector_id: string;
  tool_name: string;
  description: string;
  http_method: string;
  path_template: string;
}

interface TestResult {
  status: number | null;
  truncated: boolean;
  error: string | null;
  raw: string;
  asModelSees: string;
}

const METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"];

const EMPTY_CONNECTOR = {
  name: "",
  baseUrl: "",
  headerName: "Authorization",
  headerValue: "Bearer {{secret}}",
  secret: "",
};

const EMPTY_TOOL = {
  toolName: "",
  description: "",
  pathTemplate: "/",
  httpMethod: "GET",
  schemaText: `{
  "type": "object",
  "properties": {
    "order_id": { "type": "string", "description": "Numărul comenzii" }
  },
  "required": ["order_id"]
}`,
  responseInstructions: "",
};

export function ConnectorsScreen() {
  const t = useTranslations("agentScreens.connectorsScreen");

  const [data, setData] = useState<{
    connectors: Connector[];
    tools: Tool[];
  } | null>(null);
  const [draft, setDraft] = useState(EMPTY_CONNECTOR);
  const [tool, setTool] = useState(EMPTY_TOOL);
  const [openFor, setOpenFor] = useState("");
  const [testInput, setTestInput] = useState('{"order_id":"SB-1042"}');
  const [testing, setTesting] = useState("");
  const [result, setResult] = useState<TestResult | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setData(
        await engineApi.get<{ connectors: Connector[]; tools: Tool[] }>(
          "connectors",
        ),
      );
    } catch (err) {
      reportEngineError(err, setError);
      setData({ connectors: [], tools: [] });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const guard = async (fn: () => Promise<unknown>) => {
    setError("");
    try {
      await fn();
      await load();
    } catch (err) {
      reportEngineError(err, setError);
    }
  };

  if (data === null) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 size={14} className="animate-spin" aria-hidden="true" />
        {t("loading")}
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <p
          role="alert"
          className="rounded-card border border-danger/25 bg-danger/12 px-5 py-3 text-sm text-danger"
        >
          {error}
        </p>
      )}

      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("newHeading")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("addressChecked")}
        </p>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1.5 text-sm">
            {t("name")}
            <Input
              placeholder={t("namePlaceholder")}
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
          </label>
          <label className="grid gap-1.5 text-sm">
            {t("baseUrl")}
            <Input
              placeholder="https://api.example.com"
              value={draft.baseUrl}
              onChange={(e) => setDraft({ ...draft, baseUrl: e.target.value })}
            />
          </label>
          <label className="grid gap-1.5 text-sm">
            {t("headerName")}
            <Input
              value={draft.headerName}
              onChange={(e) =>
                setDraft({ ...draft, headerName: e.target.value })
              }
            />
          </label>
          <label className="grid gap-1.5 text-sm">
            {t("headerValue")}
            <Input
              value={draft.headerValue}
              onChange={(e) =>
                setDraft({ ...draft, headerValue: e.target.value })
              }
            />
          </label>
          <label className="grid gap-1.5 text-sm sm:col-span-2">
            {t("secret")}
            <Input
              type="password"
              placeholder={t("secretPlaceholder")}
              value={draft.secret}
              onChange={(e) => setDraft({ ...draft, secret: e.target.value })}
            />
          </label>
        </div>

        <p className="mt-3 text-sm text-muted-foreground">
          {t("secretEncrypted")}
        </p>

        <Button
          className="mt-4"
          disabled={!draft.name.trim() || !draft.baseUrl.trim()}
          onClick={() =>
            void guard(async () => {
              await engineApi.send("connectors", "POST", {
                name: draft.name,
                baseUrl: draft.baseUrl,
                headersTemplate: draft.headerName
                  ? { [draft.headerName]: draft.headerValue }
                  : {},
                secret: draft.secret,
              });
              setDraft(EMPTY_CONNECTOR);
            })
          }
        >
          {t("create")}
        </Button>
      </section>

      {data.connectors.map((connector) => {
        const tools = data.tools.filter((x) => x.connector_id === connector.id);
        const open = openFor === connector.id;

        return (
          <section key={connector.id} className="rounded-card border bg-card">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3">
              <div className="min-w-0">
                <h2 className="truncate text-sm font-medium">
                  {connector.name}
                </h2>
                <p className="truncate text-sm text-muted-foreground">
                  {connector.base_url}
                  {connector.has_secret && ` · ${t("secretSet")}`}
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                title={t("remove")}
                aria-label={t("remove")}
                onClick={() =>
                  void guard(() =>
                    engineApi.send(`connectors/${connector.id}`, "DELETE"),
                  )
                }
              >
                <Trash2 size={15} aria-hidden="true" />
              </Button>
            </div>

            {tools.length === 0 ? (
              <p className="px-5 py-6 text-sm text-muted-foreground">
                {t("noTools")}
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {tools.map((item) => (
                  <li
                    key={item.id}
                    className="flex flex-wrap items-start gap-x-4 gap-y-2 px-5 py-3"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium">{item.tool_name}</p>
                      <p className="text-sm text-muted-foreground">
                        {item.description}
                      </p>
                    </div>
                    <p className="shrink-0 text-sm tabular-nums text-muted-foreground">
                      {item.http_method} {item.path_template}
                    </p>
                    <div className="flex shrink-0 gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={testing === item.id}
                        onClick={() =>
                          void guard(async () => {
                            setTesting(item.id);
                            setResult(null);
                            try {
                              setResult(
                                await engineApi.send<TestResult>(
                                  `tools/${item.id}/test`,
                                  "POST",
                                  {
                                    input: JSON.parse(testInput),
                                  },
                                ),
                              );
                            } finally {
                              setTesting("");
                            }
                          })
                        }
                      >
                        {testing === item.id ? t("testing") : t("test")}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        title={t("remove")}
                        aria-label={t("remove")}
                        onClick={() =>
                          void guard(() =>
                            engineApi.send(`tools/${item.id}`, "DELETE"),
                          )
                        }
                      >
                        <Trash2 size={15} aria-hidden="true" />
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            <div className="border-t px-5 py-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setOpenFor(open ? "" : connector.id)}
              >
                {open ? t("cancel") : t("addTool")}
              </Button>
            </div>

            {open && (
              <div className="grid gap-3 border-t px-5 py-4">
                <label className="grid gap-1.5 text-sm">
                  {t("toolName")}
                  <Input
                    placeholder="stare_comanda"
                    value={tool.toolName}
                    onChange={(e) =>
                      setTool({ ...tool, toolName: e.target.value })
                    }
                  />
                </label>
                <label className="grid gap-1.5 text-sm">
                  {t("toolDescription")}
                  <Input
                    placeholder={t("toolDescriptionPlaceholder")}
                    value={tool.description}
                    onChange={(e) =>
                      setTool({ ...tool, description: e.target.value })
                    }
                  />
                </label>
                {/* Единственное, по чему бот решает, брать инструмент или нет. */}
                <p className="text-sm text-muted-foreground">
                  {t("descriptionMatters")}
                </p>

                <div className="flex gap-2">
                  <select
                    aria-label={t("method")}
                    className="h-9 rounded-control border bg-transparent px-2 text-sm"
                    value={tool.httpMethod}
                    onChange={(e) =>
                      setTool({ ...tool, httpMethod: e.target.value })
                    }
                  >
                    {METHODS.map((m) => (
                      <option key={m}>{m}</option>
                    ))}
                  </select>
                  <Input
                    className="flex-1"
                    aria-label={t("path")}
                    placeholder="/orders/{order_id}"
                    value={tool.pathTemplate}
                    onChange={(e) =>
                      setTool({ ...tool, pathTemplate: e.target.value })
                    }
                  />
                </div>

                <label className="grid gap-1.5 text-sm">
                  {t("params")}
                  <Textarea
                    rows={8}
                    className="font-mono text-xs"
                    value={tool.schemaText}
                    onChange={(e) =>
                      setTool({ ...tool, schemaText: e.target.value })
                    }
                  />
                </label>
                <label className="grid gap-1.5 text-sm">
                  {t("responseInstructions")}
                  <Input
                    value={tool.responseInstructions}
                    onChange={(e) =>
                      setTool({ ...tool, responseInstructions: e.target.value })
                    }
                  />
                </label>

                <Button
                  className="justify-self-start"
                  onClick={() =>
                    void guard(async () => {
                      let inputSchema: Record<string, unknown>;
                      try {
                        inputSchema = JSON.parse(tool.schemaText) as Record<
                          string,
                          unknown
                        >;
                      } catch (err) {
                        // Своя фраза, а не сырое сообщение разборщика: человек
                        // правил параметры, и ему нужно знать это, а не позицию байта.
                        // Это ошибка разбора JSON, а не отказ движка.
                        throw new Error(
                          `${t("badParams")}: ${(err as Error).message}`,
                        );
                      }
                      await engineApi.send("tools", "POST", {
                        ...tool,
                        connectorId: connector.id,
                        inputSchema,
                      });
                      setTool(EMPTY_TOOL);
                    })
                  }
                >
                  {t("saveTool")}
                </Button>
              </div>
            )}
          </section>
        );
      })}

      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("testHeading")}</h2>
        <label className="mt-3 grid gap-1.5 text-sm">
          {t("testParams")}
          <Textarea
            rows={3}
            className="font-mono text-xs"
            value={testInput}
            onChange={(e) => setTestInput(e.target.value)}
          />
        </label>

        {result && (
          <div className="mt-4 space-y-3">
            <p className="text-sm text-muted-foreground">
              HTTP {result.status ?? "—"}
              {result.truncated && ` · ${t("truncated")}`}
              {result.error && (
                <span className="text-danger"> · {result.error}</span>
              )}
            </p>
            {/* Оба ответа рядом: чужая система может ответить исправно, а бот
                всё равно не увидеть в её ответе того, что нужно. */}
            <div>
              <p className="text-sm text-muted-foreground">{t("rawAnswer")}</p>
              <pre className="mt-1 overflow-x-auto rounded-control border bg-muted/40 p-3 text-xs">
                {result.raw || t("emptyAnswer")}
              </pre>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t("asBotSees")}</p>
              <pre className="mt-1 overflow-x-auto rounded-control border bg-muted/40 p-3 text-xs">
                {result.asModelSees}
              </pre>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
