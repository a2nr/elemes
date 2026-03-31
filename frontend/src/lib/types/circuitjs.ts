/**
 * Interface for CircuitJS1 simulator API exposed via iframe's window.CircuitJS1.
 * Methods marked optional (?) may not exist depending on CircuitJS version.
 */
export interface CircuitJSApi {
	/** Import circuit from text format */
	importCircuit(text: string, showMessage: boolean): void;

	/** Export current circuit as text */
	exportCircuit(): string;

	/** Set simulation running state */
	setSimRunning(running: boolean): void;

	/** Force circuit update/redraw */
	updateCircuit(): void;

	/** Get voltage at a named node */
	getNodeVoltage(nodeName: string): number;

	/** Alternative import methods (version-dependent) */
	setCircuitText?(text: string): void;
	setupText?(text: string): void;
}
