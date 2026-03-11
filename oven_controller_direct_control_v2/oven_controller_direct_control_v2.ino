// Arduino burn in oven controller

// How to use:

// Open a serial connection to the controller (115200 baud)
//
// Serial commands are sent to the arduino in the form of two integers
// separated by a comma: A,B
// where A is the address, and B is the command.
//
/*  Address space for registers  (not all of these are well developed)
    0:    enable_run
    1:    min_temperature in °C
    2:    max_temperature in °C
    3:    enable_heater (0 to disable, 1 to enable)
    4:    DB_power (turns on all "enabled" power supplies (see below). 0 to disable, 1 to enable)
    5:    enable DB LV supply 0 (allows power supply 0 to be enabled. 0 to disable, 1 to enable)
    6:    enable DB LV supply 1 (allows power supply 1 to be enabled. 0 to disable, 1 to enable)
    7:    enable DB LV supply 2 (allows power supply 2 to be enabled. 0 to disable, 1 to enable)
    8:    enable DB LV supply 3 (allows power supply 3 to be enabled. 0 to disable, 1 to enable)
    9:    requested number of burnin hours: run_hours
    10:   requested number of burnin minutes in addition to the hours: run_minutes
    11:   read_settings (If 1, returns the current settings)
    12:   reserved
    13:   voltage_read_enable
    14:   temp_read_enable  (If 1, returns a calibrated oven temperature from the thermocouple)
    15:   debug_mode_enable
*/

const int BoardLED = 13;
const int Mux[] = { 50, 52, 53 };
const int Led[] = { 40, 41, 42, 43, 44, 45 };

// Relay[5] controls the fan
// Relay[6] controls the heater
// Relay[7] controls the heater note both heaters are controlled at once, need two relays due to power
const int Relay[] = { 29, 28, 27, 26, 25, 24, 23, 22 };
// Arduino channel to read Oven temperature probe
const int Temp = A0; 
// Arduino channels to read external voltages
const int Voltage[] = { A6, A7, A8, A9, A10, A11, A12, A13, A14, A15 };

const float temp_offset = 2.35;

char *ptr;

// Variables
int i, j, k, n;



// Configuration registers;
int command, parameter;
String inputString = "";         // A String to hold incoming serial data entered by user on Serial Monitor
char mystring[200];
bool NewCommand = false;

// Temperature related variables
float target_temperature = 25; // in °C
// now compute min_temperature and max_temperature from target temperature
float min_temperature = target_temperature - 3; // in °C -> Minimum temperature to count as burn-in
float max_temperature = target_temperature + 3; // in °C -> Overtemperature threshold -> go to idle beyond that point
float temp_calibrated; // temperature translated from ADC counts into °C
int temperature; // temperature in ADC counts
int overtemp = 0;
int temp_read_enable;


int blinky = 0;
int enable_run = 0;
int enable_heater = 0;
int enable_lv_power = 0;
int debug_mode = 0;
int enable_db_lv_supply[] = { 0, 0, 0, 0 };
int voltage_read_enable = 0;
int read_settings = 0;

// duration of the burn-in run
int requested_run_hours = 0;
int requested_run_minutes = 0;
//
unsigned long startMilTime; // time counters in milliseconds
int currentAccruedBurninMinutes = 0;
int pastAccruedBurninMinutes =0;
bool burninDone = false;
unsigned long start_mil_running_time; // time counters in milliseconds
unsigned long running_time = 0;

int address, volts, inByte;
float fvolts;


int state = 0;  // 0-idle, 1-warmup, 2-burnin. 3-cooldown, 4-debug

char c;

void setup() {
  // initialize serial port:
  inputString.reserve(200);
  Serial.begin(115200);


  //
  Serial.println("");
  Serial.println("DB Oven: Start setup ...");
  for (i = 0; i < 8; i++) {
    pinMode(Relay[i], INPUT);
    digitalWrite(Relay[i], HIGH);
  }
  for (i = 0; i < 6; i++) pinMode(Led[i], OUTPUT);

  for (i = 0; i < 3; i++) pinMode(Mux[i], OUTPUT);

  pinMode(BoardLED, OUTPUT);


  /*while (Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
    }
  */

  /*  Set up default run parameters.

      Temperatures (about 15 ADC counts per 10 degrees)
        60 degrees = 1819mV or 388 ADC counts
        70 degrees = 1679mV or 358 ADC counts
        80 degrees = 1539mV or 328 ADC counts
        90 degrees = 1399mV or 298 ADC counts
  */
  
  // requested burnin time
  requested_run_hours = 0;
  requested_run_minutes = 1;

  // initialize timer:
  SetupTimer();
  k = 0;

  Serial.println("DB Oven: Finished setup, starting in state=Idle");
  Serial.println("Waiting for user commands");
}

void checkBurninDone(){
  if (burninDone) {
    burninDone= false;
    currentAccruedBurninMinutes=0;
    pastAccruedBurninMinutes=0;
    Serial.println("Resetting Burning Done to 0!");
  }
}

void loop() {
  if (TCNT5 < 12000) {

    TCNT5 = 63974; // 0.1 second interval

    // Check for commands;

    command = -1;

    if (NewCommand) {

      inputString.toCharArray(mystring, 100);

      ptr = strchr(mystring, ',');
      if (ptr == NULL)
      {
        command = -1;
        Serial.println("Not a proper command - printing help...");
        Help();
      }
      else
      {
        // replace comma by string terminator
        *ptr = '\0';
        //convert to integer, skip first character
        command = atoi(&mystring[0]);

        // if you need to keep your string original
        // restore the comma
        *ptr = ',';

        // increment pointer to point to character after comma
        ptr++;
        // convert to integer
        parameter = atoi(ptr);
      }

      Serial.print(command);
      Serial.print("/");
      Serial.println(parameter);

      // clear the string:
      inputString = "";
      NewCommand = false;
    }

    if (command >= 0) {
      if (debug_mode == 1) Serial.print(" Executing ");
      if (debug_mode == 1) Serial.println(command);
      switch (command) {

        /*  Address space for registers
            0:    enable_run
            1:    min_temperature
            2:    max_temperature
            3:    enable_heater
            4:    enable_lv_power
            5:    enable DB LV supply 0
            6:    enable DB LV supply 1
            7:    enable DB LV supply 2
            8:    enable DB LV supply 3
            9:    requested burnin time: run_hours
            10:   requested burnin time: run_minutes
            11:   read_settings
            12:   reserved
            13:   voltage_read_enable
            14:   temp_read_enable
            15:   debug_mode

            Special debug modes:

            20:
            21:

        */

        case 0: // set enable_run and restart state machine
          if(burninDone){
            Serial.println("BurninDone=1, you can reset this by setting times or temperatures ;)");
          } else {
            voltage_read_enable = parameter;
            if(parameter==0) {
                enable_run = 0;
                state = 0;
                Serial.println("Disabling run and going idle!");
              }
            else { enable_run = 1; };
            state = 0;
            }
          break;

        case 1: // min_temperature
          checkBurninDone();
          min_temperature = parameter;
          if (min_temperature> max_temperature) {
            max_temperature=min_temperature+6;
          }
          target_temperature = (max_temperature + min_temperature)/2 ; // in °C -> Minimum temperature to count as burn-in

          Serial.print("Setting minimum burn-in temperature to: ");
          Serial.print(min_temperature);
          Serial.println(" °C");
          Serial.print("Setting oven maximum temperature to: ");
          Serial.print(max_temperature);
          Serial.println(" °C");
          Serial.print("Setting oven target temperature temperature to: ");
          Serial.print(target_temperature);
          Serial.println(" °C");          
          break;

        case 2: // max_temperature
          checkBurninDone();
          max_temperature = parameter;
          if (min_temperature> max_temperature) {
            min_temperature=max_temperature-6;
          }
          target_temperature = (max_temperature + min_temperature)/2 ; // in °C -> Minimum temperature to count as burn-in          
          Serial.print("Setting minimum burn-in temperature to: ");
          Serial.print(min_temperature);
          Serial.println(" °C");
          Serial.print("Setting oven maximum temperature to: ");
          Serial.print(max_temperature);
          Serial.println(" °C");
          Serial.print("Setting oven target temperature temperature to: ");
          Serial.print(target_temperature);
          Serial.println(" °C");          
          break;


        case 3: // enable_heater
          enable_heater = parameter;
          if (debug_mode == 1) {
            Serial.print(" Enable heater: ");
          }
          if (debug_mode == 1) Serial.println(parameter);
          break;

        case 4: // enable_lv_power
          enable_lv_power = parameter;
          if (debug_mode == 1) {
            Serial.print(" Enable power supplies: ");
          }
          if (debug_mode == 1) Serial.println(parameter);

          break;

        case 5: // enable DB LV supply 0
          enable_db_lv_supply[0] = parameter;
          if (debug_mode == 1) {
            Serial.print(" DB LV Power supply 0: ");
          }
          if (debug_mode == 1) Serial.println(parameter);
          break;

        case 6: // enable DB LV supply 1
          enable_db_lv_supply[1] = parameter;
          if (debug_mode == 1) {
            Serial.print(" DB LV Power supply 1: ");
          }
          if (debug_mode == 1) Serial.println(parameter);

          break;

        case 7: // enable DB LV supply 2
          enable_db_lv_supply[2] = parameter;
          if (debug_mode == 1) {
            Serial.print(" DB LV Power supply 2: ");
          }
          if (debug_mode == 1) Serial.println(parameter);

          break;

        case 8: // enable DB LV supply 3
          if (debug_mode == 1) {
            Serial.print(" DB LV Power supply 3: ");
          }
          if (debug_mode == 1) Serial.println(parameter);
          enable_db_lv_supply[3] = parameter;
          break;

        case 9: // run_hours
          checkBurninDone();
          requested_run_hours = parameter;
          Serial.print(" Setting number of requested burn-in hours to : ");
          Serial.println(requested_run_hours);
          break;

        case 10: // run_minutes
          checkBurninDone();
          requested_run_minutes = parameter;
          Serial.print(" Setting number of requested burn-in minutes to : ");
          Serial.println(requested_run_minutes);
          break;

        case 11: // read back settings
          read_settings = parameter;
          break;

        case 12: // reserved
          checkBurninDone();
          target_temperature = parameter;
          if ((target_temperature < min_temperature+1) || (target_temperature > max_temperature-1)) {
            min_temperature=target_temperature-3;
            max_temperature=target_temperature+3;
          }
          Serial.print("Setting minimum burn-in temperature to: ");
          Serial.print(min_temperature);
          Serial.println(" °C");
          Serial.print("Setting oven maximum temperature to: ");
          Serial.print(max_temperature);
          Serial.println(" °C");
          Serial.print("Setting oven target temperature temperature to: ");
          Serial.print(target_temperature);
          Serial.println(" °C");          
          break;

        case 13: // voltage_read_enable
          voltage_read_enable = parameter;
          break;

        case 14: // temp_read_enable
          temp_read_enable = parameter;
          break;

        case 15: // debug_mode
          if (parameter == 0) {
            Serial.print(" Exiting debug mode ");
          }
          debug_mode = parameter;
          if (debug_mode == 1) {
            Serial.println(" Entering debug mode ");
          }

          break;

        default:

          break;

      }

    }


    // Oven control state machine

    temperature = analogRead(Temp);
    temp_calibrated = (((temperature * (4980.0 / 1023)) - 2365.0) / ((1399.0 - 2365.0) / (90.0 - 20.0))) + 20.0 - temp_offset;

  

    switch (state) {
      case 0: // idle
        
        // blinking LEDs while in idle state
        if (blinky == 0) {
          blinky = 1;
          for (i = 0; i < 4; i++) digitalWrite(Led[i], HIGH);
          //Serial.println("-----------------------------------");
        }
        else {
          blinky = 0;
          for (i = 0; i < 4; i++) digitalWrite(Led[i], LOW);
        }
        
        enable_heater = 0;
        enable_lv_power = 0;
        startMilTime = millis();

        if ( (!burninDone) && (enable_run == 1) ) {
          Serial.println("Switching to state=warm-up");
          state = 1;
          running_time=0;
          start_mil_running_time= millis();}
        if (debug_mode == 1) state = 4;

        break;

      case 1: // warmup
        running_time = (millis() - start_mil_running_time) / 1000.0;
        enable_heater = 1;
        enable_lv_power = 0;

        // Use calibrated temperature (raw temperature readings are an inverse scale)
        // switch from State=warm-up to State=Burnin when temperature is high enough
        if (temp_calibrated > min_temperature) {
          state = 2;
          startMilTime = millis(); // keep track of the time when we enter burnin state
          Serial.print("Current temperature (°C) is ");
          Serial.print(temp_calibrated);
          Serial.println(" --> Switching to State = burn-in.");
        }
        
        if (debug_mode == 1) {
          Serial.print("temp_calibrated = ");
          Serial.println(temp_calibrated);
        }
        if (debug_mode == 1) state = 4;
        break;

      case 2: // burn-in
       
        running_time = (millis() - start_mil_running_time) / 1000.0;

        enable_heater = 1;
        enable_lv_power =  1;
        
        // Go to State = Idle if the accrued total burnin time has reached the required burnin duration
        currentAccruedBurninMinutes = pastAccruedBurninMinutes + millisec2minutes(millis()-startMilTime);
        if (currentAccruedBurninMinutes > (requested_run_minutes + 60* requested_run_hours)-1 ) {
            state = 0 ;
            burninDone = true;
            enable_run = 0;
            Serial.print  ("pastAccruedBurninMinutes = ");
            Serial.println(pastAccruedBurninMinutes);
            Serial.print  ("currentAccruedBurninMinutes = ");
            Serial.println(currentAccruedBurninMinutes);
            Serial.print  ("total required burnin minutes = ");
            Serial.println(requested_run_minutes + 60* requested_run_hours);
            Serial.println("Burnin completed, going to Idle - Make sure to reset Arduino for the next batch!");
            Serial.println("================================================================================");
        }

        // Go to State = Idle if overtemperature condition
        if (temp_calibrated > max_temperature) { // Max temperature exceeded. Disable run and set overtemp flag
          enable_run = 0;
          overtemp = 1;
          state = 0;
          Serial.print("Overtemperarure: ");
          Serial.print(temp_calibrated); Serial.println(" °C");
          Serial.println("Reached overtemperature, going idle !");
          
          // keep track of how much burnin was done so far
          pastAccruedBurninMinutes = pastAccruedBurninMinutes + millisec2minutes(millis()-startMilTime);

          Serial.print  ("total accrued burnin minutes = ");
          Serial.println(pastAccruedBurninMinutes);
          
          Serial.print  ("total required burnin minutes = ");
          Serial.println(requested_run_minutes + 60* requested_run_hours);
          
          Serial.println("Burnin not completed, but going to Idle - Restart cycle (0,1) when overtemperature condition is resolved!");
        }

        // Go to State ="Warmup" if T<Tmin-1 
        if (temp_calibrated < min_temperature-1) { // "-1" to avoid oscillations when Toven is just at threshold which give quick on/off/on..
          state = 1;
          enable_run = 1;
          enable_heater = 1;
          enable_lv_power = 0;
          overtemp = 0;
          
          Serial.print("Undertemperature: ");
          Serial.print(temp_calibrated); Serial.println(" °C");
          Serial.println("... going back to State=\"Warmup\" !");
          
          // keep track of how much burnin was done so far
          pastAccruedBurninMinutes = pastAccruedBurninMinutes + millisec2minutes(millis()-startMilTime);

          Serial.print  ("total accrued burnin minutes = ");
          Serial.println(pastAccruedBurninMinutes);
          
          Serial.print  ("total required burnin minutes = ");
          Serial.println(requested_run_minutes + 60* requested_run_hours);
 
        }


        break;

      case 3: // cooldown
        
        running_time = (millis() - start_mil_running_time) / 1000.0;

        enable_heater = 0;
        enable_lv_power = 0;
        // hours = 0;
        // minutes = 0;

        if (temp_calibrated <= min_temperature) state = 0; // Temperature below min burn-in temperature. Go to idle state but mantain registers
        if (debug_mode == 1) state = 4;

        break;

      default: // debug mode
        enable_run = 0;
        if (debug_mode == 0) state = 0;
    }


    // Status LED:

    if (k == 1) digitalWrite(BoardLED, LOW); else digitalWrite(BoardLED, HIGH);

    // Relays and relay indicator LEDs:

    for (j = 0; j < 4; j++) {
      if ((enable_lv_power == 1) && (enable_db_lv_supply[j] == 1)) {
        digitalWrite(Led[j], HIGH);
        pinMode(Relay[j], OUTPUT);
        digitalWrite(Relay[j], LOW);
      }
      else {
        if (state > 0) digitalWrite(Led[j], LOW);
        pinMode(Relay[j], INPUT);
        digitalWrite(Relay[j], HIGH);
      }
    }

    // Turn on crate fans if 10V power is enabled

    if (enable_lv_power == 1) {
      pinMode(Relay[5], OUTPUT);
      digitalWrite(Relay[5], LOW);
    }
    else {
      if (state > 0) digitalWrite(Led[j], LOW);
      pinMode(Relay[5], INPUT);
      digitalWrite(Relay[5], HIGH);
    }

    // Overtemp indicator LED
    if (overtemp == 1) digitalWrite(Led[5], HIGH); else digitalWrite(Led[5], LOW);

    // Heater and heater indicator LED:

    if (enable_heater == 1) {
      digitalWrite(Led[4], HIGH);
      pinMode(Relay[6], OUTPUT);
      pinMode(Relay[7], OUTPUT);
      digitalWrite(Relay[6], LOW);
      digitalWrite(Relay[7], LOW);
    }
    else {
      digitalWrite(Led[4], LOW);
      pinMode(Relay[6], INPUT);
      pinMode(Relay[7], INPUT);
      digitalWrite(Relay[6], HIGH);
      digitalWrite(Relay[7], HIGH);
    }

    // Update readout multiplexer counter:

    k = k + 1;
    if (k > 7) k = 0;


    // Drive multiplexer pins:

    for (j = 0; j < 8; j++) {
      n = MuxAdd(k, j);
      if (n > 0) digitalWrite(Mux[j], HIGH); else digitalWrite(Mux[j], LOW);
    }


    // Read out temperature:
    /*
        We calibrate to the range 20C - 90C.
        At 20C, Vout = 2365 mV.
        At 90C, Vout = 1399 mV.
        See LMT87 manual for more information
    */
    if (temp_read_enable > 0) {
      temp_calibrated = (((temperature * (4980.0 / 1023)) - 2365.0) / ((1399.0 - 2365.0) / (90.0 - 20.0))) + 20.0 - temp_offset;
      Serial.println();
      Serial.print("DB Oven temperature = ");
      Serial.print(temperature);
      Serial.print(" ADC counts, ");
      Serial.print(temp_calibrated);
      Serial.println(" °C");
      temp_read_enable = 0;
    }

    // Read out voltages:

    if (voltage_read_enable > 0 ) {
      Serial.println("Printing the voltages readout on analog inputs A6 to A15: ");
      for (j = 0; j < 10; j++) {
        // conversion from ADC counts to Volts for ATMega2560 see https://www.arduino.cc/reference/en/language/functions/analog-io/analogread/
        Serial.print("Channel ");
        Serial.print(j);
        Serial.print(": ");
        volts = analogRead(Voltage[j]);
        Serial.print("   ADC counts: ");
        Serial.print(volts);
        Serial.print(" Volts: ");
        Serial.println(0.0048828125*volts);

        //Serial.println("ADC counts:",volts," Volts: ",0.0048828125*volts);
      }
      Serial.println("");
      voltage_read_enable = 0;
    }  // end voltage_read_enable

    // Read run settings:
    if (read_settings > 0) {
      if (read_settings == 1) {
        Serial.println("");
        Serial.println("DB Oven current settings and status:");
        Serial.print  ("   Temperature settings (min/max) ");
        Serial.print  (min_temperature);
        Serial.print  (" / ");
        Serial.print  (max_temperature);
        Serial.println(" °C");

        Serial.print  ("   Target temperature °C ");
        Serial.println(target_temperature);  
        
        Serial.print  ("   Current temperature Oven °C ");
        Serial.println(temp_calibrated);  
        
        Serial.print  ("   Requested run time settings (hours : mins : total in mns) ");
        Serial.print  (requested_run_hours);
        Serial.print  (" : ");
        Serial.print  (requested_run_minutes);
        Serial.print  (" : ");
        Serial.println(requested_run_minutes + 60* requested_run_hours);
        
        Serial.print("Running Time: ");
        Serial.println(running_time);
        
        Serial.print  ("   Accrued Burn-in time since start of burn-in (minutes): ");
        Serial.println(currentAccruedBurninMinutes); // + millisec2minutes(millis()-startMilTime) ); // removed by piro...
      
        Serial.print  ("   In debug mode: ");
        Serial.println(debug_mode);

        Serial.print  ("   State (0-idle, 1-warmup, 2-burnin. 3-cooldown, 4-debug): ");
        Serial.println(state);

        Serial.print  ("   enable_run = ");
        Serial.println(enable_run);

        Serial.print  ("   enable_heater = ");
        Serial.println(enable_heater);

        Serial.print  ("   DB LV Supply 0 enabled: ");
        Serial.println(enable_db_lv_supply[0]);
        Serial.print  ("   DB LV Supply 1 enabled: ");
        Serial.println(enable_db_lv_supply[1]);
        Serial.print  ("   DB LV Supply 2 enabled: ");
        Serial.println(enable_db_lv_supply[2]);
        Serial.print  ("   DB LV Supply 3 enabled: ");
        Serial.println(enable_db_lv_supply[3]);

        Serial.print  ("   Burnin done: ");
        Serial.println(burninDone);
      } else if (read_settings==2)
      {
        Serial.print("Tmin=");
        Serial.print(min_temperature);
        Serial.print(" | Tmax=");
        Serial.print(max_temperature);
        Serial.print(" | Ttarget=");
        Serial.print(target_temperature);
        Serial.print(" | Toven=");
        Serial.print(temp_calibrated);
        Serial.print(" | RunHours=");
        Serial.print(requested_run_hours);
        Serial.print(" | RunMins=");
        Serial.print(requested_run_minutes);
        Serial.print(" | RunTotalMins=");
        Serial.print(requested_run_minutes + 60 * requested_run_hours);
        Serial.print(" | BurninAccruedMins=");
        Serial.print(currentAccruedBurninMinutes); // + millisec2minutes(millis()-startMilTime) );
        Serial.print(" | RunningTime=");
        Serial.print(running_time);
        Serial.print(" | Debug=");
        Serial.print(debug_mode);
        Serial.print(" | State=");
        Serial.print(state);
        Serial.print(" | EnableRun=");
        Serial.print(enable_run);
        Serial.print(" | EnableHeater=");
        Serial.print(enable_heater);
        Serial.print(" | LV0=");
        Serial.print(enable_db_lv_supply[0]);
        Serial.print(" | LV1=");
        Serial.print(enable_db_lv_supply[1]);
        Serial.print(" | LV2=");
        Serial.print(enable_db_lv_supply[2]);
        Serial.print(" | LV3=");
        Serial.print(enable_db_lv_supply[3]);
        Serial.print(" | BurninDone=");
        Serial.println(burninDone);
      }
      

      read_settings = 0;
    }


    // End main loop

  }
}

// monitors the serial monitor input and triggers an event if input is given - waits for newline before triggering a NewCommand
void serialEvent() {
  while (Serial.available()) {
    // get the rest of the bytes:
    char inChar = (char)Serial.read();
    // add it to the inputString:
    inputString += inChar;
    // if the incoming character is a newline, set a flag so the main loop can
    // do something about it:
    if (inChar == '\n') {
      NewCommand = true;
    }
  }
}

void SetupTimer() {
  // Use timer 5 (16 bits)
  // System clock is 16 MHz
  // When TCNT5 overflows to zero, re-load it to 3036.
  // noInterrupts();
  TCCR5A = 0;
  TCCR5B = 0;
  TCNT5 = 63974; // preload timer 65536-16MHz/256/1Hz  (Ideal count 49911, 63974 for 10 Hz);
  TCCR5B |= (1 << CS12);
  TCCR5B |= (1 << CS10);    // 1024 prescaler
}

// Functions:

int * ReadVoltages() {
  static int v[10];
  for (i = 0; i < 10; i++) v[i] = analogRead(Voltage[i]);
  return v;
}

// convert milliseconds into minutes
unsigned long millisec2seconds(unsigned long milliseconds) {
  return (milliseconds/1000.);
}

int millisec2minutes(unsigned long milliseconds) {
  milliseconds/1000.;
  return (milliseconds/1000.)/60.;
}


void SetLed(int channel, int value) {
  // Set LED
  if (value == 1) digitalWrite(Led[i], HIGH);
  else digitalWrite (Led[i], LOW);
}

int MuxAdd(int value, int BitNum) {
  int value_masked;

  // Calculate

  value_masked = value & (0x1 << BitNum);

  if (value_masked > 0) return 1; else return 0;
}

void Help()
{
  Serial.println("");
  Serial.println("Commands are of the form \"a,b\" where a=");
  Serial.println("  =0,1 to switch to state=\"warm up \" and read the values on the analog inputs (monitoring)");
  Serial.println("  =0,0 to switch to state=\"idle \" and disable power and heaters");
  Serial.println("  =1 to set the min oven temperature (°C), b=requested nin temperature value");
  Serial.println("  =2 to set the max oven temperature (°C), b=requested max temperature value ");
  Serial.println("  =3 to enable/disable the heater, b=0 disable, b=1 enable the heater ");
  Serial.println("  =4 to enable/disable power, b=0 disable, b=1 enable");
  Serial.println("  =5 to enable/disable DB LV supply 0, b=0 disable, b=1 enable");
  Serial.println("  =6 to enable/disable DB LV supply 1, b=0 disable, b=1 enable");
  Serial.println("  =7 to enable/disable DB LV supply 2, b=0 disable, b=1 enable");
  Serial.println("  =8 to enable/disable DB LV supply 3, b=0 disable, b=1 enable");
  Serial.println("  =9 to set the number of hours to run the oven, b=Nhours");
  Serial.println("  =10 to set the number of minutes to run the oven, b=Nminutes");
  Serial.println("  =11 to print the settings, b=1 otherwise settings are not printed ");
  Serial.println("  =12 Reserved");
  Serial.println("  =13 voltage_read_enable");
  Serial.println("  =14 to get the current oven temperature: 14,1");
  Serial.println("  =15 Debug mode, b=0 exit debug mode, b=1 enter debug mode");
  Serial.println("");
  Serial.println("Waiting for user commands");
}
