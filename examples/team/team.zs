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

// Not referenced by Team. It exists so tests have optional fields to exercise
// (bin_to_dict's skip_nulls); keeping it out of Team leaves Team's wire format
// untouched.
struct Contact {
    string kind;
    optional string handle;
};

struct Profile {
    string owner;
    optional string nickname;
    optional Address home;
    Contact contacts[];
};
