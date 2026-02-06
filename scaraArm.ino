#define DIR1 2
#define STEP1 3
#define DIR2 4
#define STEP2 5

void setup() {
  pinMode(DIR1, OUTPUT);
  pinMode(STEP1, OUTPUT);
  digitalWrite(DIR1, HIGH);

  pinMode(DIR2, OUTPUT);
  pinMode(STEP2, OUTPUT);
  digitalWrite(DIR2, HIGH);
}

void loop() {
  digitalWrite(STEP1, HIGH);
  delayMicroseconds(800);
  digitalWrite(STEP1, LOW);
  delayMicroseconds(800);

  digitalWrite(STEP2, HIGH);
  delayMicroseconds(800);
  digitalWrite(STEP2, LOW);
  delayMicroseconds(800);
}
