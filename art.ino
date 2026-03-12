// ===============================
// SCARA Block 2 - Arduino Uno R3
// Basic STEP/DIR Output Version
// ===============================

// ----- Motor Pins -----
#define M1_DIR 2
#define M1_STEP 3
#define M2_DIR 4
#define M2_STEP 5

// ----- Robot Geometry -----
const float L1 = 100.0;   // arm1 length (mm)
const float L2 = 100.0;   // arm2 length (mm)

// ----- Motor Specs -----
// ----- Motor Specs -----
const float STEP_ANGLE_DEG = 1.8;

// -----------------------------
// Current State Tracking (deg)
// -----------------------------
float oldA1 = 0.0;
float oldA2 = 0.0;

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
  if (isnan(feed) || feed <= 0) return 800;

  // bigger F => smaller delay => faster motion
  float d = 200000.0 / feed;

  if (d < 200) d = 200;     // fastest allowed
  if (d > 3000) d = 3000;   // slowest allowed

  return (unsigned int)d;
}

// -----------------------------
// Sync motor motion
// -----------------------------
void moveMotorsSync(long steps1, long steps2, unsigned int usDelay) {
  // your direction convention:
  // step >= 0 -> LOW
  // step < 0  -> HIGH
  digitalWrite(M1_DIR, steps1 >= 0 ? LOW : HIGH);
  digitalWrite(M2_DIR, steps2 >= 0 ? LOW : HIGH);

  long a1 = labs(steps1);
  long a2 = labs(steps2);

  long maxSteps = max(a1, a2);
  long err1 = 0;
  long err2 = 0;

  for (long i = 0; i < maxSteps; i++) {
    bool pulse1 = false;
    bool pulse2 = false;

    err1 += a1;
    if (err1 >= maxSteps) {
      err1 -= maxSteps;
      pulse1 = true;
    }

    err2 += a2;
    if (err2 >= maxSteps) {
      err2 -= maxSteps;
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
}

void loop() {
  if (!Serial.available()) return;

  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  // ---------------------------
  // Motion commands
  // ---------------------------
  if (line.startsWith("G0") || line.startsWith("G1")) {
    float x = readAxis(line, 'X');
    float y = readAxis(line, 'Y');
    float feed = readAxis(line, 'F');

    if (isnan(feed)) {
      if (line.startsWith("G0")) feed = 2000;  // default faster travel move
      else feed = 800;                         // default drawing move
    }

    unsigned int usDelay = feedToDelayUs(feed);

    Serial.print("pos x: ");
    Serial.print(x);
    Serial.print("  pos y: ");
    Serial.println(y);
    Serial.print("feed: ");
    Serial.print(feed);
    Serial.print("  usDelay: ");
    Serial.println(usDelay);

    if (isnan(x) || isnan(y)) {
      Serial.println("error");
      return;
    }

    float r = sqrt(x * x + y * y);

    // basic reach / divide-by-zero protection
    if (r == 0.0) {
      Serial.println("error");
      return;
    }

    // -------- A2 from your picture --------
    float c2 = (x * x + y * y - L1 * L1 - L2 * L2) / (2.0 * L1 * L2);
    c2 = clamp1(c2);
    float newA2_rad = acos(c2);

    // -------- A1 from your picture --------
    float t1 = (-x) / r;
    t1 = clamp1(t1);

    float t2 = (L1 + L2 * cos(newA2_rad)) / r;
    t2 = clamp1(t2);

    float newA1_rad = acos(t1) - acos(t2);

    // -------- convert everything to DEG --------
    float newA1 = radToDeg(newA1_rad);
    float newA2 = radToDeg(newA2_rad);

    Serial.print("newA1 (deg): ");
    Serial.print(newA1);
    Serial.print("  newA2 (deg): ");
    Serial.println(newA2);

    // -------- delta in DEG --------
    float deltaA1 = newA1 - oldA1;
    float deltaA2 = newA2 - oldA2;

    Serial.print("deltaA1 (deg): ");
    Serial.print(deltaA1);
    Serial.print("  deltaA2 (deg): ");
    Serial.println(deltaA2);

    // -------- DEG -> steps --------
    long step1 = lround(deltaA1 / STEP_ANGLE_DEG);
    long step2 = lround(deltaA2 / STEP_ANGLE_DEG);

    Serial.print("step1: ");
    Serial.print(step1);
    Serial.print("  step2: ");
    Serial.println(step2);

    // move motors
    moveMotorsSync(step1, step2, usDelay);

    // update old angles AFTER move
    oldA1 = newA1;
    oldA2 = newA2;

    Serial.println("ok_motors");
  }
  // ---------------------------
  // Non-motion commands
  // ---------------------------
  else if (line.startsWith("G21") || line.startsWith("G90") || line.startsWith("M2")) {
    Serial.println("ok_gcode");
  }

  // ---------------------------
  // Unknown command
  // ---------------------------
  else {
    Serial.println("error");
  }
}