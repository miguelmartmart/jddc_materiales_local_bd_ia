/**
 * systemReports.ts
 * ----------------
 * Factory functions for the structured [SYSTEM] messages that are fed back
 * to the AI after each command execution or save operation.
 *
 * Keeping these in one place means:
 *  - The AI's error-handling instructions in server.py reference exact strings
 *    that are guaranteed to be produced here.
 *  - Any project using this pattern can import just this file.
 *  - Changes to the report format need to happen in one place only.
 */

// ── Execution results ─────────────────────────────────────────────────────────

export function makeSuccessReport(command: string, output: string): string {
  return (
    `[SYSTEM] Execution Result for: ${command}\n` +
    `Success: True\n` +
    `Output:\n${output || '(No output)'}`
  );
}

export function makeFailureReport(
  command: string,
  output: string,
  exitCode?: number,
): string {
  return (
    `[SYSTEM] ❌ CRITICAL EXECUTION FAILURE for: ${command}\n` +
    `SUCCESS_FLAG: False\n` +
    `ERROR_TYPE: EXECUTION_ERROR\n` +
    `EXIT_CODE: ${exitCode ?? 'Unknown'}\n` +
    `ERROR_OUTPUT:\n${output}\n\n` +
    `⚠️ URGENT INSTRUCTION FOR AI:\n` +
    `The command FAILED. Do NOT say "Perfecto" or "Great". Do NOT proceed to the next step yet.\n` +
    `Your PRIORITY is to ANALYZE this error and FIX the code immediately.\n` +
    `You MUST:\n` +
    `1. Start your answer explicitly acknowledging the error (in Spanish).\n` +
    `2. Explain in 1 frase clara cuál fue la causa probable del fallo.\n` +
    `3. Reescribir el bloque COMPLETO del archivo afectado ya corregido.\n` +
    `4. Decir literalmente: "He corregido el error anterior modificando el fichero [ruta]."\n` +
    `5. Incluir al final un botón NEXT_ACTION de tipo run_command para volver a ejecutar el script corregido.`
  );
}

export function makeCancelledReport(
  command: string,
  output: string,
  exitCode?: number,
): string {
  return (
    `[SYSTEM] ❌ CRITICAL EXECUTION FAILURE for: ${command}\n` +
    `SUCCESS_FLAG: False\n` +
    `ERROR_TYPE: USER_CANCELLED\n` +
    `EXIT_CODE: ${exitCode ?? 'Unknown'}\n` +
    `ERROR_OUTPUT:\n${output}\n\n` +
    `⚠️ URGENT INSTRUCTION FOR AI:\n` +
    `The command was CANCELLED BY THE USER from the confirmation dialog.\n` +
    `This is NOT a bug in the code.\n` +
    `You MUST:\n` +
    `1. Explicitly say that the previous execution was cancelled by the user.\n` +
    `2. Confirm that the current code does NOT need changes due to this cancellation.\n` +
    `3. Offer to re-run the same command with a NEXT_ACTION run_command button.\n` +
    `4. Do NOT say "Perfecto" or "Genial" until a successful run happens after the cancellation.`
  );
}

// ── File save results ─────────────────────────────────────────────────────────

export function makeAutoSaveReport(
  filePath: string,
  success: boolean,
  error?: string,
): string {
  if (success) {
    return `[SYSTEM] Auto-Save: Successfully saved ${filePath} before execution.`;
  }
  return `[SYSTEM] Auto-Save: Failed to save ${filePath} before execution. Error: ${error ?? 'unknown'}`;
}

// ── Composite ─────────────────────────────────────────────────────────────────

/** Combine an optional save report and an execution report into the final AI message. */
export function combineReports(
  executionReport: string,
  saveReport?: string,
): string {
  if (!saveReport) return executionReport;
  return `${saveReport}\n\n${executionReport}`;
}
