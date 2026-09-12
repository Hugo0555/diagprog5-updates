const REPO = "Hugo0555/diagprog5-updates";
const MANIFEST_PATH = "diagprog5-update.json";
const BRANCH = "main";

function json(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

async function githubFetch(path, env, accept) {
  if (!env.GITHUB_TOKEN) {
    throw new Error("GITHUB_TOKEN no configurado en Cloudflare");
  }

  return fetch(
    `https://api.github.com/repos/${REPO}/contents/${path}?ref=${BRANCH}`,
    {
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: accept,
        "User-Agent": "DIAGPROG5-Updater",
      },
    }
  );
}

async function loadManifest(env) {
  const response = await githubFetch(
    MANIFEST_PATH,
    env,
    "application/vnd.github.raw+json"
  );

  if (!response.ok) {
    throw new Error(
      `No pude leer el manifest privado de GitHub (${response.status})`
    );
  }

  return response.json();
}

function authorized(request, env) {
  const expected = env.UPDATE_KEY || "";
  const received = request.headers.get("X-DIAGPROG5-UPDATE-KEY") || "";

  return expected.length > 20 && received === expected;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    try {
      if (url.pathname === "/health") {
        return json({
          ok: true,
          service: "diagprog5-updater",
          status: "online",
        });
      }

      if (url.pathname === "/" || url.pathname === "/version") {
        const manifest = await loadManifest(env);

        return json({
          ok: true,
          app: "DIAGPROG5",
          channel: manifest.channel || "admin",
          version: String(manifest.version || ""),
          required: Boolean(manifest.required),
          filename: manifest.filename || "",
          download_url: manifest.filename
            ? `${url.origin}/download`
            : "",
          sha256: manifest.sha256 || "",
          notes: manifest.notes || "",
        });
      }

      if (url.pathname === "/download") {
        if (!authorized(request, env)) {
          return json(
            {
              ok: false,
              error: "No autorizado",
            },
            401
          );
        }

        const manifest = await loadManifest(env);
        const filename = String(manifest.filename || "").trim();

        if (!filename) {
          return json(
            {
              ok: false,
              error: "El manifest no contiene filename",
            },
            409
          );
        }

        const response = await githubFetch(
          filename,
          env,
          "application/vnd.github.raw+json"
        );

        if (!response.ok) {
          return json(
            {
              ok: false,
              error: "No pude obtener la versión privada desde GitHub",
              github_status: response.status,
            },
            502
          );
        }

        const bytes = await response.arrayBuffer();

        return new Response(bytes, {
          status: 200,
          headers: {
            "Content-Type": "text/x-python; charset=utf-8",
            "Content-Disposition": `attachment; filename="${filename}"`,
            "Cache-Control": "no-store",
          },
        });
      }

      return json(
        {
          ok: false,
          error: "Ruta no encontrada",
        },
        404
      );
    } catch (error) {
      return json(
        {
          ok: false,
          error: String(error?.message || error),
        },
        500
      );
    }
  },
};
