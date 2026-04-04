plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val relayBaseUrl = providers.gradleProperty("relayBaseUrl")
    .orElse("https://relay.example.com/")
val relayAuthToken = providers.gradleProperty("relayAuthToken")
    .orElse("")
val relayMode = providers.gradleProperty("relayMode")
    .orElse("paper_harvest_v1")

android {
    namespace = "com.peter.paperharvestshare"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.peter.paperharvestshare"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
        buildConfigField("String", "RELAY_BASE_URL", "\"${relayBaseUrl.get().trimEnd('/')}\"")
        buildConfigField("String", "RELAY_AUTH_TOKEN", "\"${relayAuthToken.get()}\"")
        buildConfigField("String", "RELAY_MODE", "\"${relayMode.get()}\"")

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.activity:activity-ktx:1.9.2")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.6")
    implementation("androidx.work:work-runtime-ktx:2.9.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.6.1")
}
