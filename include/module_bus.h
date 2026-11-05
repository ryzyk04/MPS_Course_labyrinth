#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "uart_protocol.h"

// TEMPORARY: ESP32 -- UART -- wires gateway -- 5 V I2C -- puzzle nodes.
// Fixed frame fits the ATmega328P Wire buffer (32 bytes).
namespace ModuleBus {
enum Type : uint8_t { WIRES = 1, SIMON = 2, LABYRINTH = 3 };
enum Operation : uint8_t { GENERATE = 1, RESET = 2, STOP = 3, STATUS = 0x80 };
enum State : uint8_t { WAITING = 0, PLAYING = 1, SOLVED = 2, STOPPED = 3 };
constexpr uint8_t SIMON_ADDRESS = 0x11, LABYRINTH_ADDRESS = 0x12;
constexpr size_t FRAME_SIZE = 20;
struct Frame {
  uint8_t type = 0, operation = STATUS;
  uint64_t round = 0;
  uint16_t seed = 0;
  uint8_t difficulty = 0, state = WAITING;
  uint16_t errors = 0;
};
inline uint16_t crc16(const uint8_t *data, size_t size) {
  uint16_t crc = 0xFFFF;
  while (size--) {
    crc ^= *data++;
    for (uint8_t n = 0; n < 8; ++n) crc = (crc >> 1) ^ ((crc & 1) ? 0xA001 : 0);
  }
  return crc;
}
inline void encode(const Frame &f, uint8_t *out) {
  out[0] = 0xB7; out[1] = 1; out[2] = f.type; out[3] = f.operation;
  for (uint8_t i = 0; i < 8; ++i) out[4+i] = uint8_t(f.round >> (8*i));
  out[12] = uint8_t(f.seed); out[13] = uint8_t(f.seed >> 8);
  out[14] = f.difficulty; out[15] = f.state;
  out[16] = uint8_t(f.errors); out[17] = uint8_t(f.errors >> 8);
  uint16_t crc = crc16(out, 18);
  out[18] = uint8_t(crc); out[19] = uint8_t(crc >> 8);
}
inline bool decode(const uint8_t *in, size_t size, Frame &f) {
  if (size != FRAME_SIZE || in[0] != 0xB7 || in[1] != 1 ||
      crc16(in, 18) != uint16_t(in[18] | uint16_t(in[19]) << 8)) return false;
  if (in[2] < WIRES || in[2] > LABYRINTH ||
      (in[3] != GENERATE && in[3] != RESET && in[3] != STOP && in[3] != STATUS) ||
      in[14] > 2 || in[15] > STOPPED) return false;
  f.type = in[2]; f.operation = in[3]; f.round = 0;
  for (uint8_t i = 0; i < 8; ++i) f.round |= uint64_t(in[4+i]) << (8*i);
  f.seed = uint16_t(in[12] | uint16_t(in[13]) << 8);
  f.difficulty = in[14]; f.state = in[15];
  f.errors = uint16_t(in[16] | uint16_t(in[17]) << 8);
  return f.seed <= 9999 && (f.operation != GENERATE || f.round != 0);
}
// Gateway -> ESP: G:<module>:<READY|ERROR|SOLVED|ONLINE|OFFLINE>:<round>:<counter>
inline bool parseEvent(const char *line, uint8_t &module, char *event,
                       uint64_t &round, uint16_t &counter, const char *prefix = "G:") {
  size_t prefixSize = strlen(prefix);
  if (strlen(line) >= 48 || strncmp(line, prefix, prefixSize)) return false;
  char copy[48]; strcpy(copy, line);
  char *kind = strchr(copy+prefixSize, ':'); if (!kind) return false; *kind++ = 0;
  char *rid = strchr(kind, ':'); if (!rid) return false; *rid++ = 0;
  char *value = strchr(rid, ':'); if (!value) return false; *value++ = 0;
  uint8_t m;
  if (!uartParseId(copy+prefixSize, "", m) || (m != SIMON && m != LABYRINTH) ||
      !uartParseId(rid, "", round, true) || !uartParseId(value, "", counter, true)) return false;
  if (strcmp(kind,"READY") && strcmp(kind,"ERROR") && strcmp(kind,"SOLVED") &&
      strcmp(kind,"ONLINE") && strcmp(kind,"OFFLINE")) return false;
  strcpy(event, kind); module = m;
  return true;
}
}
