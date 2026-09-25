// FastAPI-compatible error responses: {"detail": "<msg>"} for HTTPException,
// {"detail": [ {type, loc, msg, input, ctx?} ]} for validation failures (422).

export class HttpError extends Error {
  // `extra` adds machine-readable keys beside `detail` (e.g. {reason} for ML
  // failures, which the app switches on rather than parsing text).
  constructor(status, detail, headers = {}, extra = {}) {
    super(typeof detail === "string" ? detail : "HttpError");
    this.status = status;
    this.detail = detail;
    this.headers = headers;
    this.extra = extra;
  }
}

export class ValidationFailure extends Error {
  constructor(errors) {
    super("validation failed");
    this.errors = errors;
  }
}

/** 404 fallback that answers 405 (with Allow) when the path exists for other methods. */
export function makeNotFoundHandler(allowedMethodsFor) {
  return (req, res) => {
    const allowed = allowedMethodsFor(req.path);
    if (allowed.length) {
      res.setHeader("Allow", allowed.join(", "));
      return res.status(405).json({ detail: "Method Not Allowed" });
    }
    return res.status(404).json({ detail: "Not Found" });
  };
}

export function errorHandler(err, _req, res, _next) {
  if (err instanceof HttpError) {
    for (const [k, v] of Object.entries(err.headers)) res.setHeader(k, v);
    return res.status(err.status).json({ detail: err.detail, ...err.extra });
  }
  if (err instanceof ValidationFailure) {
    return res.status(422).json({ detail: err.errors });
  }
  // express.json() body parse failure
  if (err && err.type === "entity.parse.failed") {
    const m = /position (\d+)/.exec(err.message ?? "");
    const pos = m ? Number(m[1]) : 0;
    return res.status(422).json({
      detail: [
        {
          type: "json_invalid",
          loc: ["body", pos],
          msg: "JSON decode error",
          input: {},
          ctx: { error: err.message },
        },
      ],
    });
  }
  console.error(err);
  return res.status(500).type("text/plain").send("Internal Server Error");
}
