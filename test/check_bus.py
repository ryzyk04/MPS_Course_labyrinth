"""Host checks of the local protocol and firmware (requires g++)."""
from pathlib import Path
import shutil
import subprocess
from host_stubs import write_uno_stubs

project = Path(__file__).resolve().parents[1]
out = project / ".pio/bus-checks"
out.mkdir(parents=True, exist_ok=True)
write_uno_stubs(out)
common = r'''
#include <cassert>
#include <cstdio>
#include <vector>
#include "puzzle_i2c.h"
void deliver(uint8_t type,uint64_t round,uint16_t seed,uint8_t difficulty,uint8_t op=ModuleBus::GENERATE) {
  ModuleBus::Frame f;f.type=type;f.operation=op;f.round=round;f.seed=seed;f.difficulty=difficulty;
  uint8_t bytes[ModuleBus::FRAME_SIZE];ModuleBus::encode(f,bytes);Wire.inject(bytes,sizeof(bytes));
}
ModuleBus::Frame response() {
  auto bytes=Wire.request();ModuleBus::Frame f;
  assert(ModuleBus::decode(bytes.data(),bytes.size(),f));return f;
}
'''
protocol = r'''
int main() {
  PuzzleI2c endpoint;endpoint.begin(ModuleBus::SIMON,ModuleBus::SIMON_ADDRESS);
  assert(response().state==ModuleBus::WAITING);
  deliver(ModuleBus::SIMON,4294967297ULL,42,2);
  assert(endpoint.status.round==0); // No work inside onReceive ISR.
  assert(endpoint.update()==PuzzleI2c::NEW_GAME);
  assert(response().round==4294967297ULL && response().seed==42 && response().difficulty==2);
  endpoint.smallError();endpoint.smallError();endpoint.solved();
  assert(response().errors==2 && response().state==ModuleBus::SOLVED);
  deliver(ModuleBus::SIMON,4294967297ULL,42,2);
  assert(endpoint.update()==PuzzleI2c::NONE && response().errors==2);
  deliver(ModuleBus::LABYRINTH,10,1234,0);
  assert(endpoint.update()==PuzzleI2c::NONE);
  ModuleBus::Frame f;f.type=ModuleBus::SIMON;f.operation=ModuleBus::GENERATE;f.round=99;
  uint8_t data[ModuleBus::FRAME_SIZE];ModuleBus::encode(f,data);
  for(unsigned i=0;i<sizeof(data);++i) {
    data[i]^=1;Wire.inject(data,sizeof(data));assert(endpoint.update()==PuzzleI2c::NONE);data[i]^=1;
  }
  Wire.inject(data,sizeof(data)-1);assert(endpoint.update()==PuzzleI2c::NONE);
  deliver(ModuleBus::SIMON,10,0,0);assert(endpoint.update()==PuzzleI2c::NEW_GAME);
  assert(response().errors==0 && response().seed==0);
  deliver(ModuleBus::SIMON,9,0,0,ModuleBus::STOP);
  assert(endpoint.update()==PuzzleI2c::NONE);
  deliver(ModuleBus::SIMON,10,0,0,ModuleBus::STOP);
  assert(endpoint.update()==PuzzleI2c::HALT && response().state==ModuleBus::STOPPED);
  endpoint.smallError();assert(response().errors==0);
  deliver(ModuleBus::SIMON,10,0,0,ModuleBus::RESET);
  assert(endpoint.update()==PuzzleI2c::HALT && response().round==0);
  uint8_t module;char event[8];uint64_t round;uint16_t count;
  assert(ModuleBus::parseEvent("G:3:ERROR:18446744073709551615:65535",module,event,round,count));
  assert(module==3 && round==UINT64_MAX && count==65535);
  assert(ModuleBus::parseEvent("E:GACK:2:SOLVED:42:0",module,event,round,count,"E:GACK:"));
  for(auto bad:{"G:1:ERROR:1:1","G:2:ERROR:1:65536","G:2:BOGUS:1:1","G:2:ERROR:-1:1","G:2:ERROR:1:1:1"})
    assert(!ModuleBus::parseEvent(bad,module,event,round,count));
  puts("PASS: CRC, deferred ISR, duplicate rounds, reset/stop, counters and UART envelopes");
}
'''
labyrinth = r'''
#include "src/main.cpp"
int main() {
  setup();assert(!gameActive && response().round==0);
  for(int d=0;d<3;++d)for(int map=0;map<9;++map) {
    uint64_t round=1+d*9+map;
    deliver(ModuleBus::LABYRINTH,round,map,d);loop();
    assert(gameActive && levelIndex==d*9+map && level.size==4+d*2);
    uint8_t sx=px,sy=py;
    tryMove(-int8_t(px)-1,0);assert(px==sx && py==sy && response().errors==1);
    deliver(ModuleBus::LABYRINTH,round,map,d);loop();assert(response().errors==1 && px==sx && py==sy);
    // All 27 mazes must have a valid route from the configured start to finish.
    bool seen[8][8]={};int qx[64],qy[64],head=0,tail=1;
    int previousX[8][8],previousY[8][8];
    qx[0]=sx;qy[0]=sy;seen[sx][sy]=true;
    const int dx[4]={0,0,-1,1},dy[4]={1,-1,0,0};
    while(head<tail) {
      int x=qx[head],y=qy[head++];
      for(int k=0;k<4;++k) {
        int nx=x+dx[k],ny=y+dy[k];
        if(nx<0||ny<0||nx>=level.size||ny>=level.size||seen[nx][ny]||wallBetween(x,y,nx,ny))continue;
        seen[nx][ny]=true;previousX[nx][ny]=x;previousY[nx][ny]=y;qx[tail]=nx;qy[tail++]=ny;
      }
    }
    assert(seen[level.finishX][level.finishY]);
    int routeX[64],routeY[64],n=0,x=level.finishX,y=level.finishY;
    while(x!=sx||y!=sy) {routeX[n]=x;routeY[n++]=y;int oldX=x;x=previousX[x][y];y=previousY[oldX][y];}
    for(int i=n-1;i>=0;--i)tryMove(routeX[i]-px,routeY[i]-py);
    loop();assert(!gameActive && response().state==ModuleBus::SOLVED && levelIndex==d*9+map);
    uint64_t saved=bus.status.round;testNow+=2000;loop();assert(bus.status.round==saved && !gameActive);
  }
  deliver(ModuleBus::LABYRINTH,100,0,0);loop();assert(gameActive);
  deliver(ModuleBus::LABYRINTH,100,0,0,ModuleBus::STOP);loop();assert(!gameActive);
  puts("PASS: labyrinth deterministic 27 maps, BFS routes, errors, duplicate commands, latched win and stop");
}
'''

compiler = shutil.which("g++")
if not compiler:
    raise SystemExit("g++ required")
for name, checks in (("protocol", protocol), ("labyrinth", labyrinth)):
    cpp = out / f"{name}.cpp"
    cpp.write_text(common + checks, encoding="utf-8")
    exe = out / f"{name}.exe"
    subprocess.run([compiler, "-std=c++17", "-O2", "-Wall", "-Wextra", "-I", str(out), "-I", str(project), "-I", str(project / "include"), str(cpp), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)