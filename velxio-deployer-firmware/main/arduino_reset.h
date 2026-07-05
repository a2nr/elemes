#pragma once

/**
 * Trigger hardware reset on Arduino via DTR pulse.
 * Must be called before serial bridge starts to ensure
 * Arduino bootloader is ready.
 */
void arduino_trigger_reset(void);
