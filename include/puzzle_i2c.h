#pragma once
#include <Arduino.h>
#include <Wire.h>
#include "uart_protocol.h"
#include "module_bus.h"

// The ISR only copies frames. Game generation, LEDs and Serial run in loop().
class PuzzleI2c {
 public:
  enum Action : uint8_t { NONE, NEW_GAME, HALT };
  ModuleBus::Frame status;
  void begin(uint8_t type, uint8_t address) {
    status.type = type;
    publish();
    instance() = this;
    Wire.begin(address);
    Wire.onReceive(receiveEvent);
    Wire.onRequest(requestEvent);
  }
  Action update() {
    uint8_t packet[ModuleBus::FRAME_SIZE];
    noInterrupts();
    bool available = pending;
    if (available) { memcpy(packet, received, sizeof(packet)); pending = false; }
    interrupts();
    if (!available) return NONE;
    ModuleBus::Frame command;
    if (!ModuleBus::decode(packet, sizeof(packet), command) || command.type != status.type) return NONE;
    if (command.operation == ModuleBus::GENERATE) {
      if (command.round == status.round) return NONE;
      status.round = command.round; status.seed = command.seed;
      status.difficulty = command.difficulty;
      status.errors = 0; status.state = ModuleBus::PLAYING;
      publish();
      return NEW_GAME;
    }
    if (command.operation == ModuleBus::RESET ||
        (command.operation == ModuleBus::STOP && command.round == status.round)) {
      status.state = command.operation == ModuleBus::RESET ? ModuleBus::WAITING : ModuleBus::STOPPED;
      if (command.operation == ModuleBus::RESET) { status.round = 0; status.errors = 0; }
      publish();
      return HALT;
    }
    return NONE;
  }
  void smallError() {
    if (status.state != ModuleBus::PLAYING) return;
    if (status.errors != UINT16_MAX) ++status.errors;
    publish();
  }
  void solved() { status.state = ModuleBus::SOLVED; publish(); }
 private:
  volatile bool pending = false;
  uint8_t received[ModuleBus::FRAME_SIZE] = {}, reply[ModuleBus::FRAME_SIZE] = {};
  static PuzzleI2c *&instance() { static PuzzleI2c *p = nullptr; return p; }
  void publish() {
    uint8_t packet[ModuleBus::FRAME_SIZE];
    ModuleBus::encode(status, packet);
    noInterrupts(); memcpy(reply, packet, sizeof(reply)); interrupts();
  }
  static void receiveEvent(int size) {
    PuzzleI2c *p = instance();
    uint8_t packet[ModuleBus::FRAME_SIZE]; uint8_t n = 0;
    while (Wire.available()) {
      uint8_t value = Wire.read();
      if (n < sizeof(packet)) packet[n++] = value;
    }
    if (p && size == int(sizeof(packet)) && n == sizeof(packet)) {
      memcpy(p->received, packet, sizeof(packet)); p->pending = true;
    }
  }
  static void requestEvent() {
    PuzzleI2c *p = instance();
    if (p) Wire.write(p->reply, sizeof(p->reply));
  }
};
