package team;

struct Address {
    string street;
    string city;
    string country;
    uint32 zipCode;
};

struct Experience {
    string company;
    string position;
    uint16 yearsWorked;
};

struct Skill {
    string name;
    uint8 level;
};

struct Person {
    string name;
    uint32 age;
    Address address;
    Experience workExperience[];
    Skill skills[];
    string hobbies[];
    string bio;
};

struct Team {
    string name;
    Person members[];
};
