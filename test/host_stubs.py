"""Small host peripherals for exercising the real Uno sketches without hardware."""
from pathlib import Path


def write_wire_stub(out: Path):
    (out / "Wire.h").write_text(r'''
#pragma once
#include <cstdint>
#include <vector>
#include <map>
#include <cstring>
struct WireStub {
  std::vector<uint8_t> rx,tx;
  std::map<int,std::vector<uint8_t>> replies,writes;
  int address=0;
  void (*receiveCallback)(int)=nullptr;
  void (*requestCallback)()=nullptr;
  void begin() {}
  void begin(uint8_t) {}
  void setClock(uint32_t) {}
  void setWireTimeout(uint32_t,bool) {}
  void onReceive(void (*fn)(int)) {receiveCallback=fn;}
  void onRequest(void (*fn)()) {requestCallback=fn;}
  void beginTransmission(uint8_t a) {address=a;tx.clear();}
  size_t write(const uint8_t *data,size_t n) {tx.insert(tx.end(),data,data+n);return n;}
  int endTransmission() {writes[address]=tx;return 0;}
  int requestFrom(uint8_t a,uint8_t) {rx=replies[a];return int(rx.size());}
  int available() {return int(rx.size());}
  int read() {int n=rx.front();rx.erase(rx.begin());return n;}
  void inject(const uint8_t *data,size_t n) {
    rx.assign(data,data+n);if(receiveCallback)receiveCallback(int(n));
  }
  std::vector<uint8_t> request() {tx.clear();requestCallback();return tx;}
};
inline WireStub Wire;
''', encoding="utf-8")


def write_uno_stubs(out: Path):
    write_wire_stub(out)
    (out / "Arduino.h").write_text(r'''
#pragma once
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <algorithm>
constexpr int HIGH=1,LOW=0,OUTPUT=1,INPUT_PULLUP=2,MSBFIRST=1;
constexpr int A0=14,A1=15,A2=16,A3=17,A4=18,A5=19;
#define F(x) x
#define PROGMEM
#define memcpy_P memcpy
inline uint32_t testNow=0;
inline int pins[20]={};
inline uint32_t millis() {return testNow;}
inline uint32_t micros() {return testNow*1000;}
inline int analogRead(int) {return 1;}
inline void delay(uint32_t t) {testNow+=t;}
inline void pinMode(int p,int mode) {if(mode==INPUT_PULLUP)pins[p]=HIGH;}
inline int digitalRead(int p) {return pins[p];}
inline void digitalWrite(int p,int v) {pins[p]=v;}
inline void analogWrite(int p,int v) {pins[p]=v;}
inline void shiftOut(int,int,int,uint8_t) {}
inline void noInterrupts() {}
inline void interrupts() {}
inline void randomSeed(uint32_t s) {srand(s);}
inline long random(long n) {return rand()%n;}
inline long random(long a,long b) {return a+random(b-a);}
struct SerialStub {
  void begin(int) {}
  template<class T> void print(T) {}
  template<class T> void println(T) {}
  void println() {}
};
inline SerialStub Serial;
''', encoding="utf-8")
    (out / "SoftwareSerial.h").write_text(r'''
#pragma once
#include <string>
#include <cstdint>
struct SoftwareSerial {
  std::string rx,tx;
  SoftwareSerial(int,int) {}
  void begin(uint32_t) {}
  int available() {return int(rx.size());}
  int read() {char c=rx[0];rx.erase(0,1);return uint8_t(c);}
  void print(const char *s) {tx+=s;}
  void print(char c) {tx+=c;}
  void print(uint32_t n) {tx+=std::to_string(n);}
  void write(char c) {tx+=c;}
  void println() {tx+='\n';}
  template<class T> void println(T value) {print(value);tx+='\n';}
};
''', encoding="utf-8")
    (out / "Adafruit_NeoPixel.h").write_text(r'''
#pragma once
#include <cstdint>
constexpr int NEO_GRB=0,NEO_KHZ800=0;
struct Adafruit_NeoPixel {
  uint32_t pixels[8]={};
  Adafruit_NeoPixel(int,int,int) {}
  void begin() {}
  void setBrightness(int) {}
  void setPixelColor(int p,uint32_t c) {pixels[p]=c;}
  void show() {}
  void clear() {for(auto &c:pixels)c=0;}
  uint32_t Color(uint8_t r,uint8_t g,uint8_t b) {return uint32_t(r)<<16|uint32_t(g)<<8|b;}
};
''', encoding="utf-8")
    (out / "TM1637Display.h").write_text(r'''
#pragma once
struct TM1637Display {
  int number=-1;
  TM1637Display(int,int) {}
  void setBrightness(int) {}
  void clear() {number=-1;}
  void showNumberDec(int n,bool) {number=n;}
};
''', encoding="utf-8")
