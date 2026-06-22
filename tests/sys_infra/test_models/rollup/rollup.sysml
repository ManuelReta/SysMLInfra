part def MassedThing {
    attribute mass :> ISQ::mass; 
    attribute totalMass :> ISQ::mass;
}

part simpleThing : MassedThing {
    attribute redefines totalMass = mass;
}

part compositeThing : MassedThing {
    import NumericalFunctions::sum; 
    
    part subcomponents: MassedThing[*];

    attribute redefines totalMass =
        mass + sum(subcomponents.totalMass); 
}

part def SpacecraftComponent :> MassedThing {
    attribute identifier: Scalarattributes::String;
}

part spacecraftSystem: SpacecraftComponent :> compositeThing {
    part subsystems[*] :> spacecraftSystem redefines subcomponents;    
}

part def PropulsionSystem :> SpacecraftComponent { 
    // ...
}

part def PowerSystem :> SpacecraftComponent { 
    // ...
}

part spacecraft :> spacecraftSystem {
    part propulsion: PropulsionSystem subsets subsystems;    
    part power: PowerSystem subsets subsystems;
    // etc...
}

part spacecraft_1 :> spacecraft {
    import SI::*;
    
    redefines mass = 1000 [kg];
    
    part redefines propulsion {
        redefines mass = 100 [kg];
    }
    
    part redefines power {
        redefines mass = 50 [kg];
        part battery subsets subsystems {
            redefines mass = 10 [kg];
        }
    }
}