#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

// Arduino AVR Print has no uint64_t overload; format IDs without heap allocations.
template<class Port> inline void uartPrintId(Port &port, uint64_t id) {
  char digits[21];
  uint8_t position = 20;
  digits[position] = '\0';
  do {
    digits[--position] = char('0' + id % 10);
    id /= 10;
  } while (id);
  port.print(digits + position);
}

// Newline-framed UART messages; reject a whole oversized frame, not its suffix.
struct UartLineReader {
  char buffer[48] = {};
  uint8_t length = 0;
  bool overflow = false;

  template<class Handler> void feed(char c, Handler handler) {
    if (c == '\r') return;
    if (c == '\n') {
      if (!overflow && length) { buffer[length] = '\0'; handler(buffer); }
      length = 0;
      overflow = false;
    } else if (!overflow) {
      if (length < sizeof(buffer) - 1) buffer[length++] = c;
      else overflow = true;
    }
  }
};

template<class Id> inline bool uartParseId(const char *line, const char *prefix, Id &id, bool allowZero = false) {
  size_t prefixLength = strlen(prefix);
  if (strncmp(line, prefix, prefixLength)) return false;
  const char *p = line + prefixLength;
  if (!*p) return false;
  Id value = 0;
  for (; *p; ++p) {
    if (*p < '0' || *p > '9') return false;
    uint8_t digit = uint8_t(*p - '0');
    if (value > (Id(-1) - digit) / 10) return false;
    value = value * 10 + digit;
  }
  if (!value && !allowZero) return false;
  id = value;
  return true;
}

inline bool uartParseGeneration(const char *line, uint64_t &id, uint16_t &seed, uint8_t &level) {
  if (strlen(line) >= 48) return false;
  char copy[48];
  strcpy(copy, line);
  const char *prefix = "E:GENERATE:";
  if (strncmp(copy, prefix, strlen(prefix))) return false;
  char *seedStart = strchr(copy + strlen(prefix), ':');
  if (!seedStart) return false;
  *seedStart++ = '\0';
  char *levelStart = strchr(seedStart, ':');
  if (!levelStart) return false;
  *levelStart++ = '\0';
  uint64_t parsedId;
  uint16_t parsedSeed;
  uint8_t parsedLevel;
  if (!uartParseId(copy, prefix, parsedId) || !uartParseId(seedStart, "", parsedSeed, true) ||
      parsedSeed > 9999 || !uartParseId(levelStart, "", parsedLevel, true) || parsedLevel > 2) return false;
  id = parsedId;
  seed = parsedSeed;
  level = parsedLevel;
  return true;
}
