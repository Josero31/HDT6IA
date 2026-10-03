/**
 * Evals de TOOL EXECUTION.
 *
 * El provider (evals/provider.py) devuelve en `metadata.tool_calls` la traza de
 * todas las herramientas ejecutadas, en orden, en los dos niveles de la
 * arquitectura centralizada:
 *
 *   { nivel: 'orquestador' | 'especialista', tool, args, ok, ms, salida, orden }
 *
 * Cada función exportada es una aserción reutilizable desde el YAML:
 *
 *   - type: javascript
 *     value: file://assertions/herramientas.js:llamada
 *     config: { tool: agendar_cita, exitosa: true, args: { hora: '08:30' } }
 *
 * En `args` y en las fechas se admite `[HOY+N]` y expresiones `re:<regex>`.
 */

function hoyMas(n) {
  const d = new Date();
  d.setDate(d.getDate() + n);
  const pad = (x) => String(x).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function resolver(valor) {
  if (typeof valor !== 'string') return valor;
  return valor.replace(/\[HOY\+(\d+)\]/g, (_, n) => hoyMas(Number(n)));
}

function normalizar(v) {
  return String(v ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim();
}

/** Compara un valor real con el esperado (igualdad flexible, `re:` o lista de opciones). */
function coincide(real, esperado) {
  if (Array.isArray(esperado)) return esperado.some((e) => coincide(real, e));
  const e = resolver(esperado);
  if (typeof e === 'string' && e.startsWith('re:')) {
    return new RegExp(e.slice(3), 'i').test(String(real ?? ''));
  }
  return normalizar(real) === normalizar(e);
}

function traza(context) {
  const meta = context.metadata || context.providerResponse?.metadata || {};
  return meta.tool_calls || [];
}

function describir(calls) {
  if (!calls.length) return '(ninguna herramienta)';
  return calls.map((c) => `${c.tool}${c.ok === false ? '✗' : ''}`).join(' → ');
}

function filtrar(calls, cfg) {
  return calls.filter(
    (c) =>
      [].concat(cfg.tool).includes(c.tool) &&
      (!cfg.nivel || c.nivel === cfg.nivel) &&
      (cfg.exitosa === undefined || (c.ok !== false) === cfg.exitosa),
  );
}

function argsCoinciden(call, esperados) {
  const fallos = [];
  for (const [clave, esperado] of Object.entries(esperados || {})) {
    const real = call.args && typeof call.args === 'object' ? call.args[clave] : undefined;
    if (!coincide(real, esperado)) fallos.push(`${clave}=${JSON.stringify(real)} (esperado ${resolver(JSON.stringify(esperado))})`);
  }
  return fallos;
}

/**
 * La herramienta `tool` (o cualquiera de una lista) se llamó al menos `min` veces (y como máximo `max`),
 * opcionalmente con los argumentos indicados y/o con resultado exitoso.
 */
module.exports.llamada = (output, context) => {
  const cfg = context.config || {};
  const calls = traza(context);
  const candidatas = filtrar(calls, cfg);
  const min = cfg.min ?? 1;
  const max = cfg.max ?? Infinity;

  if (candidatas.length < min || candidatas.length > max) {
    return {
      pass: false,
      score: 0,
      reason: `Se esperaba ${[].concat(cfg.tool).join(" | ")} entre ${min} y ${max} veces${cfg.exitosa ? ' (exitosa)' : ''}; hubo ${candidatas.length}. Traza: ${describir(calls)}`,
    };
  }
  if (cfg.args) {
    const conArgs = candidatas.filter((c) => argsCoinciden(c, cfg.args).length === 0);
    if (!conArgs.length) {
      const detalle = candidatas.map((c) => argsCoinciden(c, cfg.args).join(', ')).join(' | ');
      return { pass: false, score: 0, reason: `${cfg.tool} se llamó con argumentos incorrectos: ${detalle}` };
    }
  }
  return {
    pass: true,
    score: 1,
    reason: `${cfg.tool} llamada correctamente (${candidatas.length}x). Traza: ${describir(calls)}`,
  };
};

/** La herramienta NO se ejecutó (o, con `exitosa: true`, no se ejecutó con éxito). */
module.exports.noLlamada = (output, context) => {
  const cfg = context.config || {};
  const calls = traza(context);
  const prohibidas = filtrar(calls, cfg);
  return prohibidas.length === 0
    ? { pass: true, score: 1, reason: `${cfg.tool} no se ejecutó${cfg.exitosa ? ' con éxito' : ''}, como se esperaba.` }
    : { pass: false, score: 0, reason: `${cfg.tool} no debía ejecutarse${cfg.exitosa ? ' con éxito' : ''}. Traza: ${describir(calls)}` };
};

/**
 * Orden de ejecución: alguna de las herramientas de `antes` ocurre antes de la
 * primera llamada a `despues`. Útil para "clima/seguridad -> agenda".
 */
module.exports.orden = (output, context) => {
  const cfg = context.config || {};
  const calls = traza(context);
  const antes = [].concat(cfg.antes);
  const idxDespues = calls.findIndex((c) => c.tool === cfg.despues);
  if (idxDespues === -1) {
    return { pass: false, score: 0, reason: `${cfg.despues} nunca se llamó. Traza: ${describir(calls)}` };
  }
  const idxAntes = calls.findIndex((c) => antes.includes(c.tool));
  return idxAntes !== -1 && idxAntes < idxDespues
    ? { pass: true, score: 1, reason: `${calls[idxAntes].tool} ocurrió antes de ${cfg.despues}.` }
    : { pass: false, score: 0, reason: `Ninguna de [${antes}] ocurrió antes de ${cfg.despues}. Traza: ${describir(calls)}` };
};

/**
 * Ninguna herramienta de los especialistas falló (argumentos inválidos o
 * excepción), salvo las que pueden fallar a propósito por reglas de negocio.
 */
module.exports.sinErrores = (output, context) => {
  const cfg = context.config || {};
  const permitidas = [].concat(cfg.permitidas || []);
  const nivel = cfg.nivel || 'especialista';
  const fallidas = traza(context).filter(
    (c) => c.nivel === nivel && c.ok === false && !permitidas.includes(c.tool),
  );
  return fallidas.length === 0
    ? { pass: true, score: 1, reason: 'Todas las herramientas se ejecutaron sin error.' }
    : {
        pass: false,
        score: 0,
        reason: `Herramientas con error: ${fallidas.map((c) => `${c.tool}: ${JSON.stringify(c.salida)}`).join(' | ')}`,
      };
};

/**
 * Estado final de la agenda (efecto real de las herramientas): cuántas citas
 * quedaron y, opcionalmente, que exista una con ciertos campos.
 */
module.exports.citas = (output, context) => {
  const cfg = context.config || {};
  const meta = context.metadata || context.providerResponse?.metadata || {};
  const citas = meta.citas_finales || [];
  if (cfg.cantidad !== undefined && citas.length !== cfg.cantidad) {
    return {
      pass: false,
      score: 0,
      reason: `Se esperaban ${cfg.cantidad} citas al final y hay ${citas.length}: ${JSON.stringify(citas)}`,
    };
  }
  if (cfg.con) {
    const ok = citas.some((c) => Object.entries(cfg.con).every(([k, v]) => coincide(c[k], v)));
    if (!ok) return { pass: false, score: 0, reason: `No hay una cita con ${resolver(JSON.stringify(cfg.con))}: ${JSON.stringify(citas)}` };
  }
  if (cfg.sinDuplicados) {
    const claves = citas.map((c) => `${c.fecha} ${c.hora}`);
    if (new Set(claves).size !== claves.length) {
      return { pass: false, score: 0, reason: `Hay citas duplicadas en el mismo horario: ${claves}` };
    }
  }
  return { pass: true, score: 1, reason: `Agenda final correcta (${citas.length} citas).` };
};

/** El identificador de la cita creada aparece en la respuesta al cliente. */
module.exports.idEnRespuesta = (output, context) => {
  const meta = context.metadata || context.providerResponse?.metadata || {};
  const creadas = (meta.tool_calls || []).filter((c) => c.tool === 'agendar_cita' && c.ok !== false);
  const ids = creadas.map((c) => c.salida?.cita?.id).filter(Boolean);
  if (!ids.length) return { pass: false, score: 0, reason: 'No se creó ninguna cita.' };
  return ids.some((id) => String(output).toUpperCase().includes(id))
    ? { pass: true, score: 1, reason: `La respuesta incluye el ID ${ids.join(', ')}.` }
    : { pass: false, score: 0, reason: `La respuesta no incluye el ID de la cita (${ids.join(', ')}).` };
};

/** La respuesta menciona la fecha indicada (ISO o "D de <mes>"). */
module.exports.mencionaFecha = (output, context) => {
  const iso = resolver(context.config.fecha);
  const [, m, d] = iso.split('-').map(Number);
  const meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
    'septiembre', 'octubre', 'noviembre', 'diciembre'];
  const texto = normalizar(output);
  const pass =
    texto.includes(iso) ||
    new RegExp(`\\b${d}\\s+de\\s+${meses[m - 1]}`).test(texto) ||
    texto.includes(`${String(d).padStart(2, '0')}/${String(m).padStart(2, '0')}`) ||
    texto.includes(`${d}/${m}`);
  return { pass, score: pass ? 1 : 0, reason: pass ? `Menciona ${iso}.` : `No menciona la fecha ${iso}.` };
};
