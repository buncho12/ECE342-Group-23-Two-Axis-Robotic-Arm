// ===============================
// SCARA Block 2 - Arduino Uno R3
// Buffered Motion Queue Version
// ===============================

// ----- Motor Pins -----
#define M1_DIR  2
#define M1_STEP 3
#define M2_DIR  4
#define M2_STEP 5

// ----- Robot Geometry -----
const float L1 = 100.0;   // arm1 length (mm)
const float L2 = 100.0;   // arm2 length (mm)

// ----- Motor Specs -----
const float STEP_ANGLE_DEG = 1.8;

// -----------------------------
// Current State Tracking (deg)
// -----------------------------
float oldA1 = 0.0;
float oldA2 = 0.0;

// -----------------------------
// Motion Buffer
// -----------------------------
struct MotionPoint {
  float x;
  float y;
  float feed;
  bool isRapid;   // true = G0, false = G1
};

const int MAX_POINTS = 20;
MotionPoint motionBuffer[MAX_POINTS];
int motionCount = 0;

// -----------------------------
// Helpers
// -----------------------------
float readAxis(const String& s, char axis) {
  int i = s.indexOf(axis);
  if (i < 0) return NAN;

  int j = i + 1;
  while (j < (int)s.length() && s[j] != ' ' && s[j] != '\r' && s[j] != '\n') {
    j++;
  }
  return s.substring(i + 1, j).toFloat();
}

float clamp1(float v) {
  if (v > 1.0) return 1.0;
  if (v < -1.0) return -1.0;
  return v;
}

float radToDeg(float rad) {
  return rad * 180.0 / PI;
}

unsigned int feedToDelayUs(float feed) {
  if (feed < 100.0) feed = 100.0;
  if (feed > 3000.0) feed = 3000.0;

  unsigned int us = (unsigned int)(1200.0 - 0.45 * feed);

  if (us < 120) us = 120;
  if (us > 2000) us = 2000;

  return us;
}

// -----------------------------
// Sync motor motion
// -----------------------------
void moveMotorsSync(long steps1, long steps2, unsigned int usDelay) {
  digitalWrite(M1_DIR, steps1 >= 0 ? LOW : HIGH);
  digitalWrite(M2_DIR, steps2 >= 0 ? LOW : HIGH);

  delayMicroseconds(50);

  long a1 = labs(steps1);
  long a2 = labs(steps2);

  if (a1 == 0 && a2 == 0) return;

  long maxSteps = max(a1, a2);

  for (long i = 0; i < maxSteps; i++) {
    bool pulse1 = false;
    bool pulse2 = false;

    if (i * a1 / maxSteps < (i + 1) * a1 / maxSteps) {
      pulse1 = true;
    }

    if (i * a2 / maxSteps < (i + 1) * a2 / maxSteps) {
      pulse2 = true;
    }

    if (pulse1) digitalWrite(M1_STEP, HIGH);
    if (pulse2) digitalWrite(M2_STEP, HIGH);

    delayMicroseconds(usDelay);

    if (pulse1) digitalWrite(M1_STEP, LOW);
    if (pulse2) digitalWrite(M2_STEP, LOW);

    delayMicroseconds(usDelay);
  }
}

// -----------------------------
// Buffer operations
// -----------------------------
void clearMotionBuffer() {
  motionCount = 0;
}

bool addMotionPoint(float x, float y, float feed, bool isRapid) {
  if (motionCount >= MAX_POINTS) return false;

  motionBuffer[motionCount].x = x;
  motionBuffer[motionCount].y = y;
  motionBuffer[motionCount].feed = feed;
  motionBuffer[motionCount].isRapid = isRapid;
  motionCount++;
  return true;
}

// -----------------------------
// Execute one point
// -----------------------------
bool executeMotionPoint(const MotionPoint& p) {
  float x = p.x;
  float y = p.y;
  float feed = p.feed;

  unsigned int usDelay = feedToDelayUs(feed);

  Serial.print("EXEC x: ");
  Serial.print(x);
  Serial.print("  y: ");
  Serial.println(y);
  Serial.print("EXEC feed: ");
  Serial.print(feed);
  Serial.print("  usDelay: ");
  Serial.println(usDelay);

  float r = sqrt(x * x + y * y);

  if (r > (L1 + L2) || r < fabs(L1 - L2) || r == 0.0) {
    Serial.println("error");
    return false;
  }

  // IK
  float c2 = (x * x + y * y - L1 * L1 - L2 * L2) / (2.0 * L1 * L2);
  c2 = clamp1(c2);
  float newA2_rad = acos(c2);

  float t1 = (-x) / r;
  t1 = clamp1(t1);

  float t2 = (L1 + L2 * cos(newA2_rad)) / r;
  t2 = clamp1(t2);

  float newA1_rad = acos(t1) - acos(t2);

  float newA1 = radToDeg(newA1_rad);
  float newA2 = radToDeg(newA2_rad);

  Serial.print("newA1 (deg): ");
  Serial.print(newA1);
  Serial.print("  newA2 (deg): ");
  Serial.println(newA2);

  float deltaA1 = newA1 - oldA1;
  float deltaA2 = newA2 - oldA2;

  Serial.print("deltaA1 (deg): ");
  Serial.print(deltaA1);
  Serial.print("  deltaA2 (deg): ");
  Serial.println(deltaA2);

  long step1 = lround(deltaA1 / STEP_ANGLE_DEG);
  long step2 = lround(deltaA2 / STEP_ANGLE_DEG);

  Serial.print("step1: ");
  Serial.print(step1);
  Serial.print("  step2: ");
  Serial.println(step2);

  moveMotorsSync(step1, step2, usDelay);

  oldA1 = newA1;
  oldA2 = newA2;

  return true;
}

// -----------------------------
// Execute full buffer
// -----------------------------
bool executeMotionBuffer() {
  Serial.print("Executing buffer, points = ");
  Serial.println(motionCount);

  for (int i = 0; i < motionCount; i++) {
    Serial.print("Point ");
    Serial.println(i);

    if (!executeMotionPoint(motionBuffer[i])) {
      return false;
    }
  }
  return true;
}

void setup() {
  Serial.begin(115200);

  pinMode(M1_DIR, OUTPUT);
  pinMode(M1_STEP, OUTPUT);
  pinMode(M2_DIR, OUTPUT);
  pinMode(M2_STEP, OUTPUT);

  digitalWrite(M1_DIR, LOW);
  digitalWrite(M1_STEP, LOW);
  digitalWrite(M2_DIR, LOW);
  digitalWrite(M2_STEP, LOW);

  clearMotionBuffer();
}

void loop() {
  if (!Serial.available()) return;

  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  // ---------------------------
  // Motion commands: only STORE
  // ---------------------------
  if (line.startsWith("G0") || line.startsWith("G1")) {
    float x = readAxis(line, 'X');
    float y = readAxis(line, 'Y');
    float feed = readAxis(line, 'F');

    if (isnan(x) || isnan(y)) {
      Serial.println("error");
      return;
    }

    bool isRapid = line.startsWith("G0");

    if (isnan(feed)) {
      if (isRapid) feed = 1600;
      else feed = 800;
    }

    if (!addMotionPoint(x, y, feed, isRapid)) {
      Serial.println("error");
      return;
    }

    Serial.print("buffered x: ");
    Serial.print(x);
    Serial.print("  y: ");
    Serial.print(y);
    Serial.print("  feed: ");
    Serial.print(feed);
    Serial.print("  rapid: ");
    Serial.println(isRapid ? 1 : 0);

    Serial.println("ok_gcode");
  }

  // ---------------------------
  // Mode commands
  // ---------------------------
  else if (line.startsWith("G21") || line.startsWith("G90")) {
    Serial.println("ok_gcode");
  }

  // ---------------------------
  // End of program: EXECUTE
  // ---------------------------
  else if (line.startsWith("M2")) {
    bool ok = executeMotionBuffer();
    clearMotionBuffer();

    if (ok) Serial.println("ok_motors");
    else    Serial.println("error");
  }

  // ---------------------------
  // Unknown command
  // ---------------------------
  else {
    Serial.println("error");
  }
}