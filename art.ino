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
const float STEPS_PER_REV = 200.0;   // 1.8° NEMA16
const float MICROSTEP = 16.0;        // change if needed
const float GEAR_RATIO1 = 1;
const float GEAR_RATIO2 = 1;

float steps_per_degree = (STEPS_PER_REV * MICROSTEP) / 360.0;

// -----------------------------
// Current State Tracking
// -----------------------------
float current_theta1_deg = 0.0;
float current_theta2_deg = 0.0;


void moveMotorsSync(long steps1, long steps2, unsigned int usDelay) {
  // set dir
  digitalWrite(M1_DIR, steps1 >= 0 ? HIGH : LOW);
  digitalWrite(M2_DIR, steps2 >= 0 ? HIGH : LOW);

  long a1 = labs(steps1);
  long a2 = labs(steps2);

  long maxSteps = max(a1, a2);
  long err1 = 0, err2 = 0;

  for (long i = 0; i < maxSteps; i++) {
    bool pulse1 = false, pulse2 = false;

    err1 += a1;
    if (err1 >= maxSteps) { err1 -= maxSteps; pulse1 = true; }

    err2 += a2;
    if (err2 >= maxSteps) { err2 -= maxSteps; pulse2 = true; }

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
}

void moveMotor(int dirPin, int stepPin, long steps) {

  digitalWrite(dirPin, steps >= 0 ? HIGH : LOW);
  steps = abs(steps);

  for (long i = 0; i < steps; i++) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(800);   // controls speed
    digitalWrite(stepPin, LOW);
    delayMicroseconds(800);
  }
}

float angle1_0 = 0, angle2_0 = 0;

float readAxis(const String& s, char axis) {
  int i = s.indexOf(axis);
  if (i < 0) return NAN;
  int j = i + 1;
  while (j < (int)s.length() && s[j] != ' ' && s[j] != '\r' && s[j] != '\n') j++;
  return s.substring(i + 1, j).toFloat();
}

float clamp1(float v) {
  if (v > 1.0) return 1.0;
  if (v < -1.0) return -1.0;
  return v;
}

void loop() {

  if (Serial.available()) {

    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;

    if (line.startsWith("G0") || line.startsWith("G1")) {

      float x = readAxis(line, 'X');
      float y = readAxis(line, 'Y');

      if (!isnan(x) && !isnan(y)) {

        float angle1_1, angle2_1, deltaAngle1, deltaAngle2;
        long step1, step2;

        float r2 = x*x + y*y;
        float r  = sqrt(r2);

        // ---- IK (radians) ----
        // NOTE: this is ONE common SCARA form (elbow-down-ish). You may need +/- depending on your geometry.
        float c1 = clamp1((L1*L1 + r2 - L2*L2) / (2.0*L1*r));
        float c2 = clamp1((L1*L1 + L2*L2 - r2) / (2.0*L1*L2));

        angle1_1 = atan2(-x, y) - acos(c1);
        angle2_1 = acos(c2);

        Serial.println(String("angle1: ") + String(angle1_1, 6) + "  angle2: " + String(angle2_1, 6) + ";");

        // ---- delta (radians) ----
        deltaAngle1 = angle1_1 - angle1_0;
        deltaAngle2 = angle2_1 - angle2_0;

        // ---- radians -> steps ----
        step1 = (long)(deltaAngle1 / (2.0*PI) * STEPS_PER_REV * MICROSTEP * GEAR_RATIO1);
        step2 = (long)(deltaAngle2 / (2.0*PI) * STEPS_PER_REV * MICROSTEP * GEAR_RATIO2);
        Serial.print("step1: "); Serial.print(step1);
        Serial.print("  step2: "); Serial.println(step2);

        // save angles
        angle1_0 = angle1_1;
        angle2_0 = angle2_1;

        // i dont have motor connected to MC
        moveMotorsSync(step1, step2, 800);

        Serial.println("ok");
      }
      else {
        Serial.println("error");
      }
    }

    // ---------------------------
    // Non-motion commands
    // ---------------------------
    else if (line.startsWith("G21") || line.startsWith("G90") || line.startsWith("M2")) {

      // Just acknowledge them
      Serial.println("ok");
    }

    // ---------------------------
    // Unknown command
    // ---------------------------
    else {
      Serial.println("error");
    }
  }
}