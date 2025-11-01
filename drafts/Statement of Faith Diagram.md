---
tags:
  - type/moc
---

# Statement of Faith Diagram

```mermaid
graph TD
    %% Core
    A["**Core Gospel**<br>*(The saving message itself)*<br>[[0200 - The Gospel]]"]

    %% Ring 1 – Salvation
    B["**Ring 1 – Salvation**<br>*(What must be believed to be saved)*"]
    B1["[[0210 - Sin and Salvation]]"]
    B2["[[0220 - Who Jesus Is]]"]
    B3["[[0230 - Faith and Repentance]]"]
    B4["[[0240 - God’s Grace]]"]
    B5["[[0250 - The Cross and Resurrection]]"]

    %% Ring 2 – Result of Salvation
    C["**Ring 2 – Result of Salvation**<br>*(What happens when a person is saved)*"]
    C1["[[0260 - Union with Christ]]"]
    C2["[[0270 - New Creation and Eternal Life]]"]

    %% Ring 3 – Foundation of Salvation
    D["**Ring 3 – Foundation of Salvation**<br>*(What must be true for salvation to be true)*"]
    D1["[[The Trinity]]"]
    D2["[[Attributes of God]]"]
    D3["[[The Father’s Plan of Redemption]]"]
    D4["[[The Nature of Christ]]"]
    D5["[[The Spirit’s Work in Salvation]]"]
    D6["[[The Justice and Love of God]]"]
    D7["[[The Faithfulness of God]]"]
    D8["[[The Authority of Scripture]]"]

    %% Orbiting Doctrines
    E["**Orbiting Doctrines**<br>*(The outworking of gospel truth in life and creation)*"]
    E1["[[The Church]]"]
    E2["[[Fruits of the Spirit]]"]
    E3["[[Gifts of the Spirit]]"]
    E4["[[Sanctification and Holiness]]"]
    E5["[[Worship and Sacraments]]"]
    E6["[[Creation]]"]
    E7["[[Eschatology]]"]
    E8["[[Christian Ethics]]"]
    E9["[[Faith and Culture]]"]

    %% Relationships
    A --> B
    B --> C
    C --> D
    D --> E

    %% Sub-links
    B --> B1
    B --> B2
    B --> B3
    B --> B4
    B --> B5

    C --> C1
    C --> C2

    D --> D1
    D --> D2
    D --> D3
    D --> D4
    D --> D5
    D --> D6
    D --> D7
    D --> D8

    E --> E1
    E --> E2
    E --> E3
    E --> E4
    E --> E5
    E --> E6
    E --> E7
    E --> E8
    E --> E9

    %% Styling
    classDef core fill:#f4f1de,stroke:#3d405b,stroke-width:2px,color:#3d405b;
    classDef ring1 fill:#e07a5f,stroke:#3d405b,stroke-width:2px,color:white;
    classDef ring2 fill:#81b29a,stroke:#3d405b,stroke-width:2px,color:white;
    classDef ring3 fill:#f2cc8f,stroke:#3d405b,stroke-width:2px,color:#3d405b;
    classDef orbit fill:#a5a58d,stroke:#3d405b,stroke-width:2px,color:white;

    class A core;
    class B,B1,B2,B3,B4,B5 ring1;
    class C,C1,C2 ring2;
    class D,D1,D2,D3,D4,D5,D6,D7,D8 ring3;
    class E,E1,E2,E3,E4,E5,E6,E7,E8,E9 orbit;
